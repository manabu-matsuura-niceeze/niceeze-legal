-- NiceEze GCPネイティブ移行マイグレーション
-- Ver 2.3 — Supabase → Cloud SQL PostgreSQL 16 / BigQuery連携
--
-- 変更点:
--   1. auth.uid() → current_setting('app.current_user_id')::UUID に変更
--      （Cloud SQL はSupabase Auth拡張非対応のため、アプリ層でJWT検証後にセッション変数セット）
--   2. pg_partman → 標準RANGE パーティション宣言型へ（Cloud SQL互換）
--   3. BigQuery Foreign Data Wrapper (bigquery_fdw) 設定追加
--   4. Cloud SQL Auth Proxy接続用ロール設定
--   5. Memorystore Redis連携用の通知チャンネル（LISTEN/NOTIFY）定義

-- ─────────────────────────────────────────────
-- Cloud SQL互換: RLSポリシーをセッション変数方式に移行
-- ─────────────────────────────────────────────

-- アプリ層でJWT検証後に実行するヘルパー
CREATE OR REPLACE FUNCTION set_current_user_id(user_id UUID)
RETURNS void AS $$
BEGIN
    PERFORM set_config('app.current_user_id', user_id::TEXT, true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- RLSポリシーをCloud SQL互換に再定義
-- （Supabaseのauth.uid()をcurrent_setting方式に変更）
CREATE OR REPLACE FUNCTION current_app_user_id()
RETURNS UUID AS $$
    SELECT current_setting('app.current_user_id', true)::UUID;
$$ LANGUAGE sql STABLE;

-- ── users テーブル RLSポリシー更新 ──────────────
DROP POLICY IF EXISTS users_self_select ON users;
DROP POLICY IF EXISTS users_self_update ON users;
DROP POLICY IF EXISTS users_no_delete   ON users;

ALTER TABLE users ENABLE ROW LEVEL SECURITY;  -- ENABLE ROW LEVEL SECURITY

CREATE POLICY users_self_select ON users
    FOR SELECT USING (id = current_app_user_id());

CREATE POLICY users_self_update ON users
    FOR UPDATE USING (id = current_app_user_id());

CREATE POLICY users_no_delete ON users
    FOR DELETE USING (false);

-- ── packages テーブル RLSポリシー更新 ───────────
DROP POLICY IF EXISTS packages_owner_select ON packages;
DROP POLICY IF EXISTS packages_owner_insert ON packages;
DROP POLICY IF EXISTS packages_owner_update ON packages;

ALTER TABLE packages ENABLE ROW LEVEL SECURITY;  -- ENABLE ROW LEVEL SECURITY

CREATE POLICY packages_owner_select ON packages
    FOR SELECT USING (user_id = current_app_user_id());

CREATE POLICY packages_owner_insert ON packages
    FOR INSERT WITH CHECK (user_id = current_app_user_id());

CREATE POLICY packages_owner_update ON packages
    FOR UPDATE USING (user_id = current_app_user_id());

-- ─────────────────────────────────────────────
-- Cloud SQL標準 月次パーティション（pg_partman不要）
-- 既存の packages テーブルに月次パーティションを明示定義
-- ─────────────────────────────────────────────

-- 6ヶ月分のパーティションを事前定義（cronで毎月自動追加）
CREATE TABLE IF NOT EXISTS packages_2026_05
    PARTITION OF packages
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

CREATE TABLE IF NOT EXISTS packages_2026_06
    PARTITION OF packages
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

CREATE TABLE IF NOT EXISTS packages_2026_07
    PARTITION OF packages
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');

CREATE TABLE IF NOT EXISTS packages_2026_08
    PARTITION OF packages
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');

CREATE TABLE IF NOT EXISTS packages_2026_09
    PARTITION OF packages
    FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');

CREATE TABLE IF NOT EXISTS packages_2026_10
    PARTITION OF packages
    FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');

-- ─────────────────────────────────────────────
-- Memorystore Redis連携: LISTEN/NOTIFY チャンネル
-- Cloud Run → Cloud SQL → pg_notify → Redis Streams
-- ─────────────────────────────────────────────

-- パッケージステータス変更時にRedisへ通知するトリガー
CREATE OR REPLACE FUNCTION notify_package_status_change()
RETURNS TRIGGER AS $$
DECLARE
    payload JSON;
BEGIN
    -- Redis StreamsへのPUSH判定データを構築
    payload := json_build_object(
        'user_id',    NEW.user_id,
        'package_id', NEW.id,
        'status',     NEW.status,
        'prev_status', CASE WHEN TG_OP = 'UPDATE' THEN OLD.status ELSE NULL END,
        'changed_at', NOW()
    );
    -- pg_notify → Cloud Run Pub/Sub Bridge → Memorystore Redis XADD
    PERFORM pg_notify('package_status_channel', payload::TEXT);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER packages_status_notify
    AFTER INSERT OR UPDATE OF status ON packages
    FOR EACH ROW EXECUTE FUNCTION notify_package_status_change();

-- ─────────────────────────────────────────────
-- BigQuery連携: 月次アーカイブビュー定義
-- Cloud SQL → BigQuery Data Transfer Serviceで自動転送
-- ─────────────────────────────────────────────

-- 月次アーカイブ対象ビュー（3ヶ月超のdelivered荷物）
CREATE OR REPLACE VIEW packages_archive_candidates AS
SELECT
    id,
    user_id,
    tracking_no,
    status,
    carrier,
    actual_delivery,
    created_at,
    -- アーカイブ時はPII列を匿名化してBigQueryへ転送
    -- address_encrypted は転送しない（ZONE2 = Cloud SQL内保持）
    NULL::BYTEA AS address_encrypted,
    NULL::BYTEA AS notes_encrypted
FROM packages
WHERE
    status = 'delivered'
    AND actual_delivery < NOW() - INTERVAL '3 months'
    AND created_at < NOW() - INTERVAL '3 months';

COMMENT ON VIEW packages_archive_candidates IS
    'BigQuery転送対象: delivered済み3ヶ月超の荷物。PII列は除外済み。'
    'Cloud Scheduler + Cloud SQL → BigQuery Data Transfer で月1回実行。';

-- ─────────────────────────────────────────────
-- Cloud Run サービスアカウント用ロール設定
-- ─────────────────────────────────────────────

-- Cloud SQL Auth Proxy経由で接続するサービスアカウント用ロール
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'niceeze_api') THEN
        CREATE ROLE niceeze_api LOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'niceeze_ocr_worker') THEN
        CREATE ROLE niceeze_ocr_worker LOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'niceeze_liff_worker') THEN
        CREATE ROLE niceeze_liff_worker LOGIN;
    END IF;
END $$;

-- API Worker: SELECT/INSERT/UPDATE（DELETE不可）
GRANT SELECT, INSERT, UPDATE ON users, packages TO niceeze_api;
GRANT SELECT, INSERT ON audit_logs TO niceeze_api;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO niceeze_api;

-- OCR Worker: packagesへのINSERTのみ
GRANT SELECT ON users TO niceeze_ocr_worker;
GRANT INSERT, SELECT ON packages TO niceeze_ocr_worker;
GRANT INSERT ON audit_logs TO niceeze_ocr_worker;

-- LIFF Worker: packagesのSELECT（RLSで本人分のみ）
GRANT SELECT ON packages TO niceeze_liff_worker;
GRANT INSERT ON audit_logs TO niceeze_liff_worker;

COMMENT ON ROLE niceeze_api IS
    'Cloud Run APIサービス用ロール。Cloud SQL Auth Proxyで接続。';
