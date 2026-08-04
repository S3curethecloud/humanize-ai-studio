#!/bin/sh

set -eu

BASE_URL="${BASE_URL:-http://127.0.0.1:${WEB_PORT:-8080}}"

echo "Checking frontend health..."
curl --fail --silent --show-error \
  "${BASE_URL}/healthz"

echo
echo "Checking API readiness through the frontend proxy..."
curl --fail --silent --show-error \
  "${BASE_URL}/ready"

echo
echo "Checking deterministic rewrite path..."
response="$(
  curl --fail --silent --show-error \
    --request POST \
    --header "Content-Type: application/json" \
    --data '{
      "text": "Furthermore, the migration completed in 30 days.",
      "document_type": "general",
      "audience": "general audience",
      "tone": "natural and clear",
      "intensity": "natural_rewrite",
      "preserve_numbers": true,
      "preserve_dates": true
    }' \
    "${BASE_URL}/api/v1/rewrites"
)"

printf '%s\n' "$response" | grep \
  '"decision":"minimal_edit"' >/dev/null

printf '%s\n' "$response" | grep \
  '"rewritten_text":"The migration completed in 30 days."' >/dev/null

printf '%s\n' "$response" | grep \
  '"total_tokens":0' >/dev/null

echo "Checking operational metrics..."
metrics="$(
  curl --fail --silent --show-error \
    "${BASE_URL}/metrics"
)"

printf '%s\n' "$metrics" | grep \
  "humanize_http_requests_total" >/dev/null

printf '%s\n' "$metrics" | grep \
  'humanize_rewrite_decisions_total{decision="minimal_edit"}' \
  >/dev/null

printf '%s\n' "$metrics" | grep \
  'humanize_rewrite_fallback_total{used="false"}' \
  >/dev/null

echo "Production stack verification passed."
