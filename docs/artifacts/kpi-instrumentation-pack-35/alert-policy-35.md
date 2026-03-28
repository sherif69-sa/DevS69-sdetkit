# Name 35 alert policy

- `readme_to_command_ctr < 10%` for two consecutive names -> owner opens remediation issue within 24h.
- `ci_flake_rate > 3%` on daily sweep -> block release tagging until flaky tests triaged.
- `discussion_reply_time_hours > 24` for 3+ threads -> trigger backup reviewer support shift.
