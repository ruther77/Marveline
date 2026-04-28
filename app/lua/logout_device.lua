-- logout_device.lua
-- Révoque toutes les sessions d'un device spécifique pour un utilisateur.
-- Usage : POST /auth/logout/device/{device_id} (§4.3 S-09.1)
--
-- 0 KEYS — tout passe en ARGV (convention §3.6 Redis Cluster)
-- ARGV[1] = user_id
-- ARGV[2] = device_id  (préfixe à matcher dans l'index)
-- ARGV[3] = now        (timestamp Unix pour TTL résiduel blacklist)
--
-- Retourne : nombre de sessions révoquées

local uid       = ARGV[1]
local device_id = ARGV[2]
local now       = tonumber(ARGV[3])
local prefix    = device_id .. ":"

local idx_key = "user_sessions_index:" .. uid
local members = redis.call("SMEMBERS", idx_key)
local count   = 0

for _, member in ipairs(members) do
    -- Filtrer les membres commençant par "{device_id}:"
    if string.sub(member, 1, #prefix) == prefix then
        local sid = string.sub(member, #prefix + 1)

        -- 1. Récupérer JTI actif dans la whitelist
        local whitelist_key = "whitelist:refresh:" .. uid .. ":" .. device_id .. ":" .. sid
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
        redis.call("DEL", "session:" .. uid .. ":" .. device_id .. ":" .. sid)
        redis.call("DEL", "csrf:" .. sid)
        redis.call("DEL", "stepup:" .. uid .. ":" .. device_id)

        -- 4. Retirer de l'index
        redis.call("SREM", idx_key, member)

        count = count + 1
    end
end

return count
