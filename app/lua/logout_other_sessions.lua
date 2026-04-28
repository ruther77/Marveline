-- logout_other_sessions.lua
-- Révoque toutes les sessions d'un utilisateur SAUF la session courante.
-- Usage : password change (§4.5 S-09.3)
--
-- 0 KEYS — tout passe en ARGV (convention §3.6 Redis Cluster)
-- ARGV[1] = user_id
-- ARGV[2] = current_did  (device_id de la session à conserver)
-- ARGV[3] = current_sid  (session_id de la session à conserver)
-- ARGV[4] = now          (timestamp Unix pour TTL résiduel blacklist)
--
-- Retourne : nombre de sessions révoquées

local uid         = ARGV[1]
local current_did = ARGV[2]
local current_sid = ARGV[3]
local now         = tonumber(ARGV[4])

local exclude_member = current_did .. ":" .. current_sid
local idx_key        = "user_sessions_index:" .. uid
local members        = redis.call("SMEMBERS", idx_key)
local count          = 0

for _, member in ipairs(members) do
    if member ~= exclude_member then
        local sep = string.find(member, ":", 1, true)
        if sep then
            local did = string.sub(member, 1, sep - 1)
            local sid = string.sub(member, sep + 1)

            -- 1. Récupérer JTI actif dans la whitelist
            local whitelist_key = "whitelist:refresh:" .. uid .. ":" .. did .. ":" .. sid
            local jti = redis.call("GET", whitelist_key)

            if jti then
                -- 2. Blacklister l'access token avec TTL résiduel
                local meta_key = "jti:meta:" .. jti
                local exp_raw  = redis.call("GET", meta_key)
                if exp_raw then
                    local ttl = tonumber(exp_raw) - now
                    if ttl > 0 then
                        redis.call("SET", "blacklist:jti:" .. jti, "1", "EX", ttl)
                    end
                end
                redis.call("DEL", whitelist_key)
            end

            -- 3. Nettoyer session data + CSRF + step-up (§3.6)
            redis.call("DEL", "session:" .. uid .. ":" .. did .. ":" .. sid)
            redis.call("DEL", "csrf:" .. sid)
            redis.call("DEL", "stepup:" .. uid .. ":" .. did)

            -- 4. Retirer de l'index
            redis.call("SREM", idx_key, member)

            count = count + 1
        end
    end
end

return count
