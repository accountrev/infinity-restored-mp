/* DisneyInfinityCoop.log in the game folder: one line per event, with the time since the first line. */
static void *g_log = (void *)-1;
static char g_buf[512];
static u32 g_start_tick;

static char *put_str(char *p, char *end, const char *s)
{
    if (!s) s = "(null)";
    while (*s && p < end) *p++ = *s++;
    return p;
}

static char *put_uint(char *p, char *end, u32 v)
{
    char tmp[12];
    int n = 0;
    do { tmp[n++] = (char)('0' + v % 10); v /= 10; } while (v);
    while (n && p < end) *p++ = tmp[--n];
    return p;
}

/* printf subset: %d %u %s. Not flushed: WriteFile hands each line to the OS, so the log survives a
   game crash, and a flush per line would sync the file on the game thread. */
static void coop_log(const char *fmt, ...)
{
    __builtin_va_list ap;
    char *p = g_buf, *end = g_buf + sizeof(g_buf) - 2;
    u32 written;

    if (g_log == (void *)-1) {
        g_log = k32_CreateFileA("DisneyInfinityCoop.log", 0x40000000 /*GENERIC_WRITE*/, 1 /*SHARE_READ*/,
                                0, 2 /*CREATE_ALWAYS*/, 0x80 /*NORMAL*/, 0);
        if (g_log == (void *)-1) return;
        g_start_tick = k32_GetTickCount();
    }
    p = put_uint(p, end, k32_GetTickCount() - g_start_tick);
    p = put_str(p, end, "ms ");
    __builtin_va_start(ap, fmt);
    for (; *fmt && p < end; fmt++) {
        if (*fmt != '%') { *p++ = *fmt; continue; }
        switch (*++fmt) {
        case 'd': { int v = __builtin_va_arg(ap, int);
                    if (v < 0) *p++ = '-';
                    p = put_uint(p, end, v < 0 ? 0u - (u32)v : (u32)v); break; }
        case 'u': p = put_uint(p, end, __builtin_va_arg(ap, u32)); break;
        case 's': p = put_str(p, end, __builtin_va_arg(ap, const char *)); break;
        default:  *p++ = *fmt; break;
        }
    }
    __builtin_va_end(ap);
    *p++ = '\r';
    *p++ = '\n';
    k32_WriteFile(g_log, g_buf, (u32)(p - g_buf), &written, 0);
}
