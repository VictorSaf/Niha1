-- Reconcile orphan introducer contact requests (same logic as
-- POST /api/v1/admin/contact-requests/reconcile-introducer-orphans).
--
-- Deletes rows in contact_requests where request_flow = 'introducer' and
-- contact_email has no user with role PREINTRODUCER or INTRODUCER.
--
-- Usage (Docker):
--   docker compose exec -T db psql -U niha_user -d niha_carbon -v ON_ERROR_STOP=1 -f - < scripts/sql/reconcile_introducer_orphan_contact_requests.sql
--
BEGIN;

DELETE FROM contact_requests cr
WHERE cr.request_flow = 'introducer'
  AND NOT EXISTS (
    SELECT 1
    FROM users u
    WHERE lower(u.email) = lower(cr.contact_email)
      AND u.role IN ('PREINTRODUCER'::userrole, 'INTRODUCER'::userrole)
  );

COMMIT;
