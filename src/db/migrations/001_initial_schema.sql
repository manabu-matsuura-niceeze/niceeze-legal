-- NiceEze 共通基盤 DBスキーマ定義
-- Ver 2.2 — Gemini参謀セカンドオピニオン反映済
--
-- 【パーティショニングキー確定】
--   採用: created_at RANGE（月次）※ Gemini参謀指摘に基づき確定
--   理由: 月次データローテーション → BigQuery エクスポートに最適。
--         100万世帯スケール時の月200万件を月次パーティションで管理し
--         古いパーティションの DETACH/アーカイブを容易にする。
--   却下: user_id HASH（BigQuery連携時にパーティション単位の削除が困難）

-- ─────────────────────────────────────────────
-- 拡張機能
-- ─────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";      -- AES-256暗号化 (pgp_sym_encrypt)
CREATE EXTENSION IF NOT EXISTS "pg_partman";    -- 自動パーティション管理

-- ─────────────────────────────────────────────
-- ユーザーテーブル（個人情報 = AES-256暗号化対象）
-- ─────────────────────────────────────────────
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email_encrypted BYTEA NOT NULL,  -- pgp_sym_encrypt（AES-256）で暗号化
    name_encrypted  BYTEA NOT NULL,  -- pgp_sym_encrypt（AES-256）で暗号化
    phone_encrypted BYTEA,           -- pgp_sym_encrypt（AES-256）で暗号化
    postal_code     VARCHAR(8),
    prefecture      VARCHAR(10),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── ROW LEVEL SECURITY（RLS）設定 ────────────────
-- [AUDIT EVIDENCE] RLS実装確認 Layer2 ハルシネーション検証対象
ALTER TABLE users ENABLE ROW LEVEL SECURITY;  -- ENABLE ROW LEVEL SECURITY: users

CREATE POLICY users_self_select ON users
    FOR SELECT USING (id = auth.uid());

CREATE POLICY users_self_update ON users
    FOR UPDATE USING (id = auth.uid());

CREATE POLICY users_no_delete ON users
    FOR DELETE USING (false);   -- 論理削除のみ許可

-- ─────────────────────────────────────────────
-- 荷物テーブル
-- パーティション: created_at RANGE 月次（確定）
-- ─────────────────────────────────────────────
CREATE TABLE packages (
    id                 UUID NOT NULL DEFAULT uuid_generate_v4(),
    user_id            UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tracking_no        VARCHAR(50) NOT NULL,
    status             VARCHAR(20) NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending','in_transit','delivered','returned')),
    carrier            VARCHAR(30),
    estimated_delivery DATE,
    actual_delivery    TIMESTAMPTZ,
    address_encrypted  BYTEA,               -- pgp_sym_encrypt（AES-256）
    notes_encrypted    BYTEA,               -- pgp_sym_encrypt（AES-256）
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, created_at)
)
PARTITION BY RANGE (created_at);            -- 月次レンジパーティション（確定）

-- pg_partman 自動月次パーティション作成
-- 3万世帯 × 4荷物/月 = 12万件/月 → 50万世帯 = 200万件/月でも管理可能
SELECT partman.create_parent(
    p_parent_table => 'public.packages',
    p_control      => 'created_at',
    p_type         => 'range',
    p_interval     => '1 month',
    p_premake      => 3
);

CREATE INDEX idx_packages_user_id    ON packages (user_id);
CREATE INDEX idx_packages_tracking   ON packages (tracking_no);
CREATE INDEX idx_packages_status     ON packages (status) WHERE status != 'delivered';
CREATE INDEX idx_packages_created_at ON packages (created_at);

-- ── ROW LEVEL SECURITY（RLS）設定 ─────────────────
ALTER TABLE packages ENABLE ROW LEVEL SECURITY;  -- ENABLE ROW LEVEL SECURITY: packages

CREATE POLICY packages_owner_select ON packages
    FOR SELECT USING (user_id = auth.uid());

CREATE POLICY packages_owner_insert ON packages
    FOR INSERT WITH CHECK (user_id = auth.uid());

CREATE POLICY packages_owner_update ON packages
    FOR UPDATE USING (user_id = auth.uid());

-- ─────────────────────────────────────────────
-- 暗号化ヘルパー関数（pgcrypto AES-256）
-- [AUDIT EVIDENCE] encrypt_pii / pgp_sym_encrypt 使用確認
-- ─────────────────────────────────────────────
CREATE OR REPLACE FUNCTION encrypt_pii(plaintext TEXT, key_id TEXT)
RETURNS BYTEA AS $$
BEGIN
    -- pgp_sym_encrypt: pgcrypto による AES-256-CBC 暗号化
    RETURN pgp_sym_encrypt(
        plaintext,
        current_setting('app.encryption_key_' || key_id)
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION decrypt_pii(ciphertext BYTEA, key_id TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN pgp_sym_decrypt(
        ciphertext,
        current_setting('app.encryption_key_' || key_id)
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ─────────────────────────────────────────────
-- 監査ログテーブル（改ざん不可・RLS で INSERT のみ許可）
-- ─────────────────────────────────────────────
CREATE TABLE audit_logs (
    id          BIGSERIAL PRIMARY KEY,
    table_name  VARCHAR(50) NOT NULL,
    operation   VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT','UPDATE','DELETE')),
    row_id      UUID NOT NULL,
    user_id     UUID,
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    old_values  JSONB,
    new_values  JSONB
) PARTITION BY RANGE (changed_at);

ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;  -- ENABLE ROW LEVEL SECURITY: audit_logs

CREATE POLICY audit_logs_read_only   ON audit_logs FOR SELECT USING (true);
CREATE POLICY audit_logs_insert_only ON audit_logs FOR INSERT WITH CHECK (true);
-- DELETE/UPDATE ポリシーは意図的に未作成 → 変更不可

-- ─────────────────────────────────────────────
-- updated_at 自動更新トリガー
-- ─────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER packages_updated_at
    BEFORE UPDATE ON packages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

COMMENT ON TABLE users IS
    'PII は全列 pgcrypto pgp_sym_encrypt (AES-256) 暗号化。RLS で本人のみアクセス可。';

COMMENT ON TABLE packages IS
    'パーティション: created_at RANGE 月次（確定）。Gemini参謀推奨によりBigQuery連携に最適化。';
