-- British Auction RFQ: database schema (PostgreSQL)

-- Each carrier/supplier. name_key is the lowercase name so "Maersk" and "maersk" are one supplier.
CREATE TABLE IF NOT EXISTS suppliers (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        VARCHAR(120) NOT NULL,
    name_key    VARCHAR(120) NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per auction.
CREATE TABLE IF NOT EXISTS rfqs (
    id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reference_id            VARCHAR(64)  NOT NULL UNIQUE,
    name                    VARCHAR(200) NOT NULL,

    bid_start               TIMESTAMPTZ NOT NULL,
    bid_close               TIMESTAMPTZ NOT NULL,  -- CURRENT close time (moves when extended)
    original_bid_close      TIMESTAMPTZ NOT NULL,  -- what the buyer first set
    forced_close            TIMESTAMPTZ NOT NULL,  -- hard stop, never passed
    pickup_date             DATE NOT NULL,

    trigger_type            VARCHAR(24) NOT NULL,  -- BID_RECEIVED | ANY_RANK_CHANGE | L1_CHANGE
    trigger_window_minutes  INT NOT NULL,          -- X
    extension_minutes       INT NOT NULL,          -- Y

    -- saved copies so the listing page is fast
    extension_count         INT NOT NULL DEFAULT 0,
    bid_count               INT NOT NULL DEFAULT 0,
    lowest_total            NUMERIC(14,2),
    l1_supplier_id          BIGINT REFERENCES suppliers(id),

    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_rfq_close_after_start   CHECK (original_bid_close > bid_start),
    CONSTRAINT ck_rfq_forced_after_close  CHECK (forced_close > original_bid_close),
    CONSTRAINT ck_rfq_close_within_forced CHECK (bid_close <= forced_close),
    CONSTRAINT ck_rfq_close_never_shrinks CHECK (bid_close >= original_bid_close),
    CONSTRAINT ck_rfq_positive_xy         CHECK (trigger_window_minutes > 0 AND extension_minutes > 0),
    CONSTRAINT ck_rfq_trigger_type        CHECK (trigger_type IN ('BID_RECEIVED','ANY_RANK_CHANGE','L1_CHANGE'))
);
CREATE INDEX IF NOT EXISTS ix_rfqs_bid_close ON rfqs (bid_close);
CREATE INDEX IF NOT EXISTS ix_rfqs_bid_start ON rfqs (bid_start);

-- Every quote ever submitted. We only add rows here, never edit or delete.
CREATE TABLE IF NOT EXISTS bids (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rfq_id               BIGINT NOT NULL REFERENCES rfqs(id) ON DELETE CASCADE,
    supplier_id          BIGINT NOT NULL REFERENCES suppliers(id),

    freight_charges      NUMERIC(14,2) NOT NULL,
    origin_charges       NUMERIC(14,2) NOT NULL,
    destination_charges  NUMERIC(14,2) NOT NULL,
    total                NUMERIC(14,2) NOT NULL,  -- the price suppliers compete on
    transit_days         INT NOT NULL,
    quote_validity_days  INT NOT NULL,

    idempotency_key      VARCHAR(64),             -- lets a client safely retry a request
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_bid_amounts CHECK (
        freight_charges >= 0 AND origin_charges >= 0
        AND destination_charges >= 0 AND total > 0
    ),
    CONSTRAINT uq_bid_idempotency UNIQUE (rfq_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS ix_bids_rfq_total    ON bids (rfq_id, total, created_at);
CREATE INDEX IF NOT EXISTS ix_bids_rfq_supplier ON bids (rfq_id, supplier_id);

-- The leaderboard: each supplier's BEST bid per auction.
-- Rank = ORDER BY best_total, achieved_at (earlier bid wins a tie).
CREATE TABLE IF NOT EXISTS standings (
    rfq_id       BIGINT NOT NULL REFERENCES rfqs(id) ON DELETE CASCADE,
    supplier_id  BIGINT NOT NULL REFERENCES suppliers(id),
    best_bid_id  BIGINT NOT NULL REFERENCES bids(id),
    best_total   NUMERIC(14,2) NOT NULL,
    achieved_at  TIMESTAMPTZ NOT NULL,
    bid_count    INT NOT NULL DEFAULT 1,
    PRIMARY KEY (rfq_id, supplier_id)
);
CREATE INDEX IF NOT EXISTS ix_standings_rank ON standings (rfq_id, best_total, achieved_at);

-- Timeline shown on the details page: bids, extensions and the reason for each.
CREATE TABLE IF NOT EXISTS activity_log (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rfq_id      BIGINT NOT NULL REFERENCES rfqs(id) ON DELETE CASCADE,
    bid_id      BIGINT REFERENCES bids(id),
    kind        VARCHAR(24) NOT NULL,
    message     TEXT NOT NULL,
    details     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_activity_kind CHECK (
        kind IN ('RFQ_CREATED','BID_PLACED','EXTENSION','EXTENSION_BLOCKED')
    )
);
CREATE INDEX IF NOT EXISTS ix_activity_rfq_id ON activity_log (rfq_id, id);
