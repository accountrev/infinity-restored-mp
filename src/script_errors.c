/* UI script errors are printf'd to stdout, which goes nowhere under Proton; put them in the log. */
static int g_lua_errors;

/* replaces printf("LUA ERROR: %s\n", msg) in the script call wrapper (0x478110) */
EXPORT int CDECL coop_lua_error_hook(const char *fmt, const char *msg)
{
    if (g_lua_errors < 200) {
        g_lua_errors++;
        coop_log("LUA ERROR: %s", msg);
    }
    return 0;
}
