-- revoke_single_session.lua — CaroCorp Auth Service v3.0 (§3.6, §6.11)
-- Revoque une session specifique (DELETE /admin/sessions/{id}).
-- 0 KEYS — tout en ARGV pour compat Redis Cluster.
--
-- ARGV[1] = user_id
-- ARGV[2] = device_id
-- ARGV[3] = session_id
-- ARGV[4] = now (unix timestamp)
--
-- Retour : "OK" ou "NOT_FOUND"

local user_id    = ARGV[1]
local device_id  = ARGV[2]
local session_id = ARGV[3]
local now        = tonumber(ARGV[4])

local wl_key   = 'whitelist:refresh:' .. user_id .. ':' .. device_id .. ':' .. session_id
local sess_key = 'session:' .. user_id .. ':' .. device_id .. ':' .. session_id
local idx_key  = 'user_sessions_index:' .. user_id

local jti = redis.call('GET', wl_key)
if not jti then
  return 'NOT_FOUND'
end

-- Blacklist l'access token associe (via jti:meta)
local meta_key = 'jti:meta:' .. jti
local exp = tonumber(redis.call('GET', meta_key))
if exp then
  local ttl = exp - now
  if ttl > 0 then
    redis.call('SET', 'blacklist:jti:' .. jti, '1', 'EX', ttl)
  end
  redis.call('DEL', meta_key)
end

-- Supprimer whitelist + session + index + CSRF lié à la session (spec §04 §4.3)
redis.call('DEL', wl_key)
redis.call('DEL', sess_key)
redis.call('SREM', idx_key, device_id .. ':' .. session_id)
redis.call('DEL', 'csrf:' .. session_id)

return 'OK'
