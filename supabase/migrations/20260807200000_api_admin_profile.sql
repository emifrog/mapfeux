-- =============================================================================
-- 20260807200000 — Profil administrateur de l'appelant, exposé au schéma api
--
-- Cahier §14.1, §14.2 et §13.21.
--
-- Le rôle vit dans admin.profiles — seule source de vérité, jamais les
-- métadonnées du JWT — et le schéma admin n'est pas exposé par la Data API.
-- L'application web lit donc le profil de l'appelant, et uniquement le sien,
-- par cette fonction. `anon` n'a aucun accès : un visiteur non connecté n'a
-- pas de profil, et l'existence des comptes ne le regarde pas.
-- =============================================================================

create or replace function api.admin_profile()
returns table (
  role text,
  status text,
  display_name text,
  mfa_required boolean
)
language sql
stable
security definer
set search_path = admin, pg_temp
as $$
  select
    p.role::text,
    p.status::text,
    p.display_name,
    p.mfa_required
  from admin.profiles p
  where p.user_id = auth.uid();
$$;

comment on function api.admin_profile is
  'Profil administrateur de l''appelant (auth.uid()), ou zéro ligne. Le rôle '
  'sert à afficher et à guider ; chaque écriture le revérifie côté base. §14.2';

revoke all on function api.admin_profile() from public, anon;
grant execute on function api.admin_profile() to authenticated;
