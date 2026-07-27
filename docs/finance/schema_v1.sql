PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at TEXT NOT NULL
);

CREATE TABLE stores (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  opened_on TEXT NOT NULL,
  currency TEXT NOT NULL DEFAULT 'CNY',
  timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai'
);

CREATE TABLE source_documents (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  source_type TEXT NOT NULL,
  source_platform TEXT,
  file_name TEXT,
  content_hash TEXT NOT NULL,
  captured_at TEXT NOT NULL,
  period_start TEXT,
  period_end TEXT,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE (store_id, content_hash)
);

CREATE TABLE business_facts (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  source_document_id TEXT REFERENCES source_documents(id),
  fact_type TEXT NOT NULL,
  occurred_on TEXT NOT NULL,
  amount_minor INTEGER,
  currency TEXT NOT NULL DEFAULT 'CNY',
  dimensions_json TEXT NOT NULL DEFAULT '{}',
  confidence REAL,
  review_status TEXT NOT NULL CHECK (review_status IN ('needs_review','confirmed','rejected')),
  posting_status TEXT NOT NULL DEFAULT 'unposted' CHECK (posting_status IN ('unposted','posted','reversed')),
  dedup_key TEXT NOT NULL,
  created_at TEXT NOT NULL,
  confirmed_at TEXT,
  UNIQUE (store_id, dedup_key)
);

CREATE TABLE accounts (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  code TEXT NOT NULL,
  name TEXT NOT NULL,
  account_type TEXT NOT NULL CHECK (account_type IN ('asset','liability','equity','revenue','contra_revenue','cost','expense','management_only')),
  parent_id TEXT REFERENCES accounts(id),
  dimension_type TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  UNIQUE (store_id, code)
);

CREATE TABLE accounting_periods (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  period_start TEXT NOT NULL,
  period_end TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('open','soft_closed','closed','reopened')),
  closed_at TEXT,
  closed_by TEXT,
  UNIQUE (store_id, period_start, period_end)
);

CREATE TABLE journal_entries (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  accounting_period_id TEXT NOT NULL REFERENCES accounting_periods(id),
  business_fact_id TEXT REFERENCES business_facts(id),
  entry_date TEXT NOT NULL,
  entry_type TEXT NOT NULL CHECK (entry_type IN ('automatic','manual','adjustment','reversal','opening')),
  status TEXT NOT NULL CHECK (status IN ('draft','posted','reversed')),
  posting_key TEXT NOT NULL,
  description TEXT NOT NULL,
  reversal_of_id TEXT REFERENCES journal_entries(id),
  created_at TEXT NOT NULL,
  posted_at TEXT,
  UNIQUE (store_id, posting_key)
);

CREATE TABLE journal_lines (
  id TEXT PRIMARY KEY,
  journal_entry_id TEXT NOT NULL REFERENCES journal_entries(id),
  account_id TEXT NOT NULL REFERENCES accounts(id),
  debit_minor INTEGER NOT NULL DEFAULT 0 CHECK (debit_minor >= 0),
  credit_minor INTEGER NOT NULL DEFAULT 0 CHECK (credit_minor >= 0),
  dimensions_json TEXT NOT NULL DEFAULT '{}',
  CHECK ((debit_minor = 0 AND credit_minor > 0) OR (credit_minor = 0 AND debit_minor > 0))
);

CREATE TABLE posting_templates (
  id TEXT PRIMARY KEY,
  fact_type TEXT NOT NULL,
  version INTEGER NOT NULL,
  debit_account_code TEXT NOT NULL,
  credit_account_code TEXT NOT NULL,
  amount_expression TEXT NOT NULL,
  required_dimensions_json TEXT NOT NULL DEFAULT '[]',
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  UNIQUE (fact_type, version)
);

CREATE TABLE sales_daily (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  business_date TEXT NOT NULL,
  channel TEXT NOT NULL,
  platform TEXT,
  gross_sales_minor INTEGER,
  merchant_discount_minor INTEGER,
  platform_subsidy_minor INTEGER,
  refund_minor INTEGER,
  recognized_revenue_minor INTEGER NOT NULL,
  order_count INTEGER,
  item_count INTEGER,
  customer_count INTEGER,
  source_document_id TEXT REFERENCES source_documents(id),
  basis TEXT NOT NULL,
  UNIQUE (store_id, business_date, channel, platform, source_document_id)
);

CREATE TABLE money_movements (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  occurred_on TEXT NOT NULL,
  movement_type TEXT NOT NULL CHECK (movement_type IN ('receipt','payment','transfer','owner_investment','owner_draw','loan_in','loan_repayment')),
  amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
  from_account_id TEXT REFERENCES accounts(id),
  to_account_id TEXT REFERENCES accounts(id),
  counterparty TEXT,
  business_fact_id TEXT REFERENCES business_facts(id),
  status TEXT NOT NULL CHECK (status IN ('expected','confirmed','reconciled','void')),
  external_reference TEXT
);

-- 老板日常使用的实际资金账户。它与总账科目分离，用于回答
-- “钱具体在哪个钱包/银行卡/前老板账户”。
CREATE TABLE fund_accounts (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  account_key TEXT NOT NULL,
  name TEXT NOT NULL,
  account_kind TEXT NOT NULL CHECK (account_kind IN ('cash','bank','platform_wallet','payment_wallet','clearing')),
  owner_kind TEXT NOT NULL CHECK (owner_kind IN ('store','owner','former_owner','platform','unknown')),
  institution TEXT,
  masked_number TEXT,
  is_store_controlled INTEGER NOT NULL DEFAULT 0,
  opening_balance_minor INTEGER NOT NULL DEFAULT 0,
  effective_from TEXT,
  effective_to TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','planned','retired','unknown')),
  UNIQUE (store_id, account_key)
);

-- “实际到手营业额”是经营管理口径，不替代会计营业收入。
CREATE TABLE merchant_net_sales (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  business_date TEXT NOT NULL,
  channel TEXT NOT NULL,
  merchant_net_minor INTEGER NOT NULL CHECK (merchant_net_minor >= 0),
  reference_gross_minor INTEGER,
  source_basis TEXT NOT NULL,
  evidence_status TEXT NOT NULL CHECK (evidence_status IN ('confirmed','keruyun_only','manual','missing','permission_blocked')),
  settlement_state TEXT NOT NULL CHECK (settlement_state IN ('merchant_net_confirmed','wallet_credited','bound_bank_received','former_owner_received','former_owner_pending_transfer','store_account_received','unknown','disputed')),
  current_fund_account_id TEXT REFERENCES fund_accounts(id),
  evidence_reference TEXT,
  source_document_id TEXT REFERENCES source_documents(id),
  notes TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (store_id, business_date, channel)
);

CREATE TABLE fund_movements (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  occurred_on TEXT NOT NULL,
  amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
  movement_type TEXT NOT NULL,
  from_fund_account_id TEXT REFERENCES fund_accounts(id),
  to_fund_account_id TEXT REFERENCES fund_accounts(id),
  business_scope TEXT NOT NULL CHECK (business_scope IN ('store','personal','mixed','unknown')),
  purpose TEXT NOT NULL,
  counterparty TEXT,
  merchant_net_sale_id TEXT REFERENCES merchant_net_sales(id),
  evidence_reference TEXT,
  status TEXT NOT NULL CHECK (status IN ('expected','confirmed','reconciled','void')),
  reference TEXT NOT NULL,
  notes TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (store_id, reference)
);

CREATE TABLE debt_items (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  debt_key TEXT NOT NULL,
  lender TEXT NOT NULL,
  principal_minor INTEGER NOT NULL CHECK (principal_minor > 0),
  received_on TEXT NOT NULL,
  due_on TEXT,
  annual_rate_decimal TEXT,
  repaid_principal_minor INTEGER NOT NULL DEFAULT 0,
  repaid_interest_minor INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL CHECK (status IN ('active','settled','disputed','unknown')),
  notes TEXT,
  UNIQUE (store_id, debt_key)
);

CREATE TABLE debt_allocations (
  id TEXT PRIMARY KEY,
  debt_id TEXT NOT NULL REFERENCES debt_items(id),
  allocation_key TEXT NOT NULL,
  purpose TEXT NOT NULL,
  amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
  classification TEXT NOT NULL,
  evidence_reference TEXT,
  notes TEXT,
  UNIQUE (debt_id, allocation_key)
);

-- 原始截图/回单/账单的不可变凭证索引。业务表只保存 voucher_number 引用，
-- 原图保存在门店 evidence 目录并用 sha256 防止静默替换。
CREATE TABLE evidence_vouchers (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  voucher_key TEXT NOT NULL,
  voucher_number TEXT NOT NULL,
  business_date TEXT,
  evidence_type TEXT NOT NULL,
  channel TEXT,
  amount_minor INTEGER,
  source_sheet TEXT,
  source_cell TEXT,
  original_filename TEXT NOT NULL,
  original_path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('confirmed','pending','permission_blocked','unmatched','duplicate')),
  notes TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (store_id, voucher_key),
  UNIQUE (store_id, voucher_number)
);

CREATE TABLE receivable_payable_items (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  kind TEXT NOT NULL CHECK (kind IN ('receivable','payable')),
  counterparty TEXT NOT NULL,
  opened_on TEXT NOT NULL,
  due_on TEXT,
  original_minor INTEGER NOT NULL,
  settled_minor INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL CHECK (status IN ('open','partial','settled','overdue','disputed')),
  journal_entry_id TEXT REFERENCES journal_entries(id)
);

CREATE TABLE inventory_items (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  name TEXT NOT NULL,
  category TEXT NOT NULL CHECK (category IN ('ingredient','packaging','consumable')),
  base_unit TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE inventory_movements (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  item_id TEXT NOT NULL REFERENCES inventory_items(id),
  occurred_on TEXT NOT NULL,
  movement_type TEXT NOT NULL CHECK (movement_type IN ('opening','purchase','usage','waste','count_adjustment','return')),
  quantity REAL NOT NULL,
  unit_cost_minor INTEGER,
  source_document_id TEXT REFERENCES source_documents(id),
  business_fact_id TEXT REFERENCES business_facts(id)
);

CREATE TABLE products (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  name TEXT NOT NULL,
  sku TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  UNIQUE (store_id, sku)
);

CREATE TABLE recipes (
  id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL REFERENCES products(id),
  version INTEGER NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  status TEXT NOT NULL CHECK (status IN ('draft','confirmed','retired')),
  UNIQUE (product_id, version)
);

CREATE TABLE recipe_components (
  id TEXT PRIMARY KEY,
  recipe_id TEXT NOT NULL REFERENCES recipes(id),
  inventory_item_id TEXT NOT NULL REFERENCES inventory_items(id),
  quantity REAL NOT NULL CHECK (quantity > 0),
  waste_rate REAL NOT NULL DEFAULT 0 CHECK (waste_rate >= 0)
);

CREATE TABLE employees (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  name TEXT NOT NULL,
  role TEXT NOT NULL,
  employment_type TEXT NOT NULL CHECK (employment_type IN ('employee','owner')),
  monthly_salary_minor INTEGER NOT NULL DEFAULT 0,
  overtime_hourly_minor INTEGER NOT NULL DEFAULT 0,
  active_from TEXT NOT NULL,
  active_to TEXT
);

CREATE TABLE work_records (
  id TEXT PRIMARY KEY,
  employee_id TEXT NOT NULL REFERENCES employees(id),
  business_date TEXT NOT NULL,
  regular_hours REAL NOT NULL DEFAULT 0,
  overtime_hours REAL NOT NULL DEFAULT 0,
  review_status TEXT NOT NULL CHECK (review_status IN ('needs_review','confirmed','rejected')),
  UNIQUE (employee_id, business_date)
);

CREATE TABLE fixed_assets (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  name TEXT NOT NULL,
  acquired_on TEXT NOT NULL,
  cost_minor INTEGER NOT NULL,
  residual_minor INTEGER NOT NULL DEFAULT 0,
  useful_life_months INTEGER,
  depreciation_method TEXT,
  status TEXT NOT NULL CHECK (status IN ('draft','active','disposed'))
);

CREATE TABLE daily_close_sessions (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  business_date TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('open','awaiting_inputs','ready_for_review','closed','reopened')),
  expected_cash_minor INTEGER,
  counted_cash_minor INTEGER,
  reserve_cash_minor INTEGER,
  deposit_due_minor INTEGER,
  merchant_net_confirmed INTEGER NOT NULL DEFAULT 0,
  fund_locations_reviewed INTEGER NOT NULL DEFAULT 0,
  outflows_reviewed INTEGER NOT NULL DEFAULT 0,
  inputs_json TEXT NOT NULL DEFAULT '{}',
  missing_inputs_json TEXT NOT NULL DEFAULT '[]',
  closed_at TEXT,
  UNIQUE (store_id, business_date)
);

CREATE TABLE metric_snapshots (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  metric_code TEXT NOT NULL,
  metric_version TEXT NOT NULL,
  period_start TEXT NOT NULL,
  period_end TEXT NOT NULL,
  dimension_json TEXT NOT NULL DEFAULT '{}',
  value_decimal TEXT,
  status TEXT NOT NULL CHECK (status IN ('confirmed','estimated','incomplete','conflicted')),
  blocking_reasons_json TEXT NOT NULL DEFAULT '[]',
  source_entry_ids_json TEXT NOT NULL DEFAULT '[]',
  calculated_at TEXT NOT NULL
);

CREATE TABLE metric_definitions (
  metric_code TEXT NOT NULL,
  version INTEGER NOT NULL,
  name TEXT NOT NULL,
  formula_expression TEXT NOT NULL,
  basis TEXT NOT NULL,
  required_inputs_json TEXT NOT NULL DEFAULT '[]',
  blocking_rules_json TEXT NOT NULL DEFAULT '[]',
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  PRIMARY KEY (metric_code, version)
);

CREATE TABLE financial_targets (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  target_type TEXT NOT NULL,
  period_start TEXT NOT NULL,
  period_end TEXT NOT NULL,
  amount_minor INTEGER,
  ratio_decimal TEXT,
  status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE alert_events (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  alert_code TEXT NOT NULL,
  severity TEXT NOT NULL CHECK (severity IN ('info','warning','critical')),
  business_date TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('open','acknowledged','resolved')),
  evidence_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  resolved_at TEXT
);

CREATE TABLE audit_logs (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  actor_type TEXT NOT NULL,
  actor_id TEXT,
  action TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  before_json TEXT,
  after_json TEXT,
  reason TEXT,
  created_at TEXT NOT NULL
);

-- 财务经营系统：账单导入、待确认记账、逐笔对账和未来资金计划。
-- 这些表记录资金事实与审核状态；正式损益仍由 journal_entries 计算。
CREATE TABLE finance_import_batches (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  source_type TEXT NOT NULL,
  account_key TEXT NOT NULL,
  original_filename TEXT NOT NULL,
  original_path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  row_count INTEGER NOT NULL DEFAULT 0,
  inflow_minor INTEGER NOT NULL DEFAULT 0,
  outflow_minor INTEGER NOT NULL DEFAULT 0,
  opening_balance_minor INTEGER,
  closing_balance_minor INTEGER,
  status TEXT NOT NULL CHECK (status IN ('parsed','needs_review','confirmed','failed','duplicate')),
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (store_id, sha256, account_key)
);

CREATE TABLE bookkeeping_records (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  transaction_date TEXT NOT NULL,
  transaction_time TEXT,
  direction TEXT NOT NULL CHECK (direction IN ('inflow','outflow','transfer')),
  amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
  transaction_kind TEXT NOT NULL,
  business_scope TEXT NOT NULL CHECK (business_scope IN ('store','personal','mixed','unknown')),
  category_code TEXT,
  category_name TEXT NOT NULL,
  account_key TEXT,
  counter_account_key TEXT,
  counterparty TEXT,
  summary TEXT,
  source_type TEXT NOT NULL,
  source_reference TEXT NOT NULL,
  voucher_id TEXT REFERENCES evidence_vouchers(id),
  import_batch_id TEXT REFERENCES finance_import_batches(id),
  confidence TEXT NOT NULL CHECK (confidence IN ('high','medium','low','confirmed')),
  classification_reason TEXT,
  raw_data_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL CHECK (status IN ('draft','needs_review','confirmed','posted','rejected','duplicate')),
  reconciliation_status TEXT NOT NULL DEFAULT 'unmatched',
  fingerprint TEXT NOT NULL,
  fund_movement_id TEXT REFERENCES fund_movements(id),
  journal_entry_id TEXT REFERENCES journal_entries(id),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (store_id, fingerprint)
);

CREATE TABLE finance_reconciliation_links (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  bookkeeping_record_id TEXT NOT NULL REFERENCES bookkeeping_records(id),
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  matched_amount_minor INTEGER NOT NULL CHECK (matched_amount_minor > 0),
  match_method TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('matched','partial','rejected')),
  notes TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (bookkeeping_record_id, target_type, target_id)
);

CREATE TABLE cash_plan_items (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  due_date TEXT NOT NULL,
  flow_type TEXT NOT NULL CHECK (flow_type IN ('expected_inflow','required_outflow')),
  amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
  category TEXT NOT NULL,
  counterparty TEXT,
  priority TEXT NOT NULL CHECK (priority IN ('must_pay','expected','optional')),
  status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','confirmed','paid','cancelled')),
  source_reference TEXT NOT NULL,
  notes TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (store_id, source_reference)
);

CREATE INDEX idx_facts_store_date ON business_facts(store_id, occurred_on);
CREATE INDEX idx_entries_store_date ON journal_entries(store_id, entry_date);
CREATE INDEX idx_lines_account ON journal_lines(account_id);
CREATE INDEX idx_sales_store_date ON sales_daily(store_id, business_date);
CREATE INDEX idx_money_store_date ON money_movements(store_id, occurred_on);
CREATE INDEX idx_merchant_net_store_date ON merchant_net_sales(store_id, business_date);
CREATE INDEX idx_fund_movements_store_date ON fund_movements(store_id, occurred_on);
CREATE INDEX idx_evidence_vouchers_store_date ON evidence_vouchers(store_id, business_date);
CREATE INDEX idx_bookkeeping_store_date ON bookkeeping_records(store_id, transaction_date);
CREATE INDEX idx_cash_plan_store_due ON cash_plan_items(store_id, due_date);
CREATE INDEX idx_metrics_lookup ON metric_snapshots(store_id, metric_code, period_start, period_end);
