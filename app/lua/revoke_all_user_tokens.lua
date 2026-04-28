-- revoke_all_user_tokens.lua — CaroCorp Auth Service v3.0 (§2.7, §3.6)
-- Revoque toutes les sessions d'un utilisateur.
-- Utilise par POST /auth/logout/all et RB-01.
-- 0 KEYS — tout en ARGV pour compat Redis Cluster.
--
-- ARGV[1] = user_id
-- ARGV[2] = now (unix timestamp)
--
-- Retour : nombre de sessions revoquees (integer)

local user_id  = ARGV[1]
local now      = tonumber(ARGV[2])
local idx_key  = 'user_sessions_index:' .. user_id
local sessions = redis.call('SMEMBERS', idx_key)
local count    = 0

for _, session_ref in ipairs(sessions) do
  -- session_ref = "device_id:session_id"
  local sep = string.find(session_ref, ':', 1, true)
  local did = sep and string.sub(session_ref, 1, sep - 1) or session_ref
  local sid = sep and string.sub(session_ref, sep + 1) or ''

  -- P1-12 : cle whitelist = user_id:device_id:session_id (4 segments, pas 3)
  local wl_key = 'whitelist:refresh:' .. user_id .. ':' .. did .. ':' .. sid
  local jti    = redis.call('GET', wl_key)
  if jti then
    local meta_key = 'jti:meta:' .. jti
    local exp      = tonumber(redis.call('GET', meta_key))
    if exp then
      local ttl = exp - now
      if ttl > 0 then
        redis.call('SET', 'blacklist:jti:' .. jti, '1', 'EX', ttl)
      end
      redis.call('DEL', meta_key)
    end
    redis.call('DEL', wl_key)
    count = count + 1
  end

  -- Supprimer session data + CSRF + step-up (sessions orphelines §3.6)
  redis.call('DEL', 'session:' .. user_id .. ':' .. did .. ':' .. sid)
  redis.call('DEL', 'csrf:' .. sid)
  redis.call('DEL', 'stepup:' .. user_id .. ':' .. did)
end

redis.call('DEL', idx_key)
return count
