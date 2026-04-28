-- refresh_check_v3.lua — CaroCorp Auth Service v3.0 (§2.6, §3.6)
-- Verification atomique whitelist + rotation refresh token.
-- 0 KEYS — tout en ARGV pour compat Redis Cluster.
--
-- ARGV[1] = jti (JTI du refresh token soumis)
-- ARGV[2] = user_id
-- ARGV[3] = device_id
-- ARGV[4] = session_id
-- ARGV[5] = family_id
-- ARGV[6] = now (unix timestamp)
-- ARGV[7] = new_jti (JTI du nouveau refresh token)
--
-- Retours :
--   "OK:{new_jti}"      — rotation legitime effectuee
--   "REPLAY_DETECTED"    — ancien JTI reutilise, famille revoquee
--   "TOKEN_INVALID"      — JTI inconnu

local jti        = ARGV[1]
local user_id    = ARGV[2]
local device_id  = ARGV[3]
local session_id = ARGV[4]
local family_id  = ARGV[5]
local now        = tonumber(ARGV[6])
local new_jti    = ARGV[7]

local wl_key  = 'whitelist:refresh:' .. user_id .. ':' .. device_id .. ':' .. session_id
local fam_key = 'family:' .. family_id
local idx_key = 'user_sessions_index:' .. user_id

local current_jti = redis.call('GET', wl_key)

if current_jti == jti then
  -- REFRESH LEGITIME : rotation atomique
  redis.call('SET', wl_key, new_jti)
  redis.call('SADD', fam_key, new_jti)
  return 'OK:' .. new_jti

else
  local in_family = redis.call('SISMEMBER', fam_key, jti)
  if in_family == 1 then
    -- REPLAY DETECTE : revoquer toute la famille
    local members = redis.call('SMEMBERS', fam_key)
    for _, member_jti in ipairs(members) do
      local meta_key = 'jti:meta:' .. member_jti
      local exp = tonumber(redis.call('GET', meta_key))
      if exp then
        local ttl = exp - now
        if ttl > 0 then
          redis.call('SET', 'blacklist:jti:' .. member_jti, '1', 'EX', ttl)
        end
        redis.call('DEL', meta_key)
      end
    end
    redis.call('DEL', wl_key)
    redis.call('DEL', fam_key)
    redis.call('SREM', idx_key, device_id .. ':' .. session_id)
    return 'REPLAY_DETECTED'
  else
    return 'TOKEN_INVALID'
  end
end
