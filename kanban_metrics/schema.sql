CREATE TABLE IF NOT EXISTS jira_instance (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    auth_type TEXT NOT NULL,
    verify_ssl INTEGER NOT NULL DEFAULT 1,
    user_email TEXT,
    secret TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS config (
    id TEXT PRIMARY KEY,
    jira_instance_id TEXT NOT NULL,
    name TEXT NOT NULL,
    scope_type TEXT NOT NULL,
    board_id TEXT,
    project_keys_json TEXT NOT NULL DEFAULT '[]',
    issue_types_json TEXT NOT NULL DEFAULT '[]',
    base_jql TEXT NOT NULL DEFAULT '',
    extra_jql TEXT NOT NULL DEFAULT '',
    date_range_days INTEGER,
    sync_start_date TEXT,
    sync_end_date TEXT,
    start_status_ids_json TEXT NOT NULL,
    done_status_ids_json TEXT NOT NULL,
    active_status_ids_json TEXT NOT NULL,
    attribution_mode TEXT NOT NULL,
    board_mapping_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (jira_instance_id) REFERENCES jira_instance(id)
);

CREATE TABLE IF NOT EXISTS issue (
    issue_id TEXT PRIMARY KEY,
    config_id TEXT NOT NULL,
    issue_key TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    project_key TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    initial_status_id TEXT NOT NULL,
    current_status_id TEXT NOT NULL,
    initial_assignee_account_id TEXT,
    current_assignee_account_id TEXT,
    raw_json TEXT,
    FOREIGN KEY (config_id) REFERENCES config(id)
);

CREATE TABLE IF NOT EXISTS changelog_event (
    id TEXT PRIMARY KEY,
    config_id TEXT NOT NULL,
    issue_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    at TEXT NOT NULL,
    from_id TEXT,
    to_id TEXT,
    author_account_id TEXT,
    raw_json TEXT,
    FOREIGN KEY (config_id) REFERENCES config(id),
    FOREIGN KEY (issue_id) REFERENCES issue(issue_id)
);

CREATE TABLE IF NOT EXISTS sync_job (
    id TEXT PRIMARY KEY,
    config_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    progress REAL NOT NULL,
    message TEXT NOT NULL,
    FOREIGN KEY (config_id) REFERENCES config(id)
);

CREATE INDEX IF NOT EXISTS idx_issue_config_id ON issue(config_id);
CREATE INDEX IF NOT EXISTS idx_changelog_issue_id ON changelog_event(issue_id);
CREATE INDEX IF NOT EXISTS idx_changelog_config_id ON changelog_event(config_id);
CREATE INDEX IF NOT EXISTS idx_sync_job_config_id ON sync_job(config_id);
