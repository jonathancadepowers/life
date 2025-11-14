# Cronometer CLI

A command-line tool that exports daily nutrition data from Cronometer.com and outputs it as JSON.

## Building

```bash
cd nutrition/cronometer_cli
go mod download
go build -o cronometer_export
```

## Usage

```bash
./cronometer_export \
  -username "your_email@example.com" \
  -password "your_password" \
  -start "2024-01-01" \
  -end "2024-01-31"
```

## Arguments

- `-username`: Cronometer account email (required)
- `-password`: Cronometer account password (required)
- `-start`: Start date in YYYY-MM-DD format (optional, defaults to 30 days ago)
- `-end`: End date in YYYY-MM-DD format (optional, defaults to today)

## Output

The tool outputs JSON array of daily nutrition summaries:

```json
[
  {
    "date": "2024-01-15",
    "calories": 1850.5,
    "fat": 65.2,
    "carbs": 180.3,
    "protein": 120.1
  }
]
```

## Dependencies

- [gocronometer](https://github.com/jrmycanady/gocronometer) - Go library for Cronometer API access
