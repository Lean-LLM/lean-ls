/*
 * lean-ls: GNU-style native listing (liszt) + explicit lla enrichment.
 * No new option semantics are introduced into the ordinary GNU ls path.
 * Copyright (c) 2026 lean-ls contributors. GPL-3.0-or-later.
 */
#include "lean_ls_dispatch.h"

#include <errno.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#ifdef __linux__
#include <sys/auxv.h>
#endif

enum mode { MODE_NATIVE, MODE_LLA, MODE_STRICT };

static bool
starts_option(const char *arg, const char *name)
{
    size_t n = strlen(name);
    return strncmp(arg, name, n) == 0 && (arg[n] == '\0' || arg[n] == '=');
}

/* Only unambiguous lla-only LONG options. Short flags remain GNU ls flags.
 * Detect these even if earlier operands are present (GNU option permutation).
 * After --, all arguments are ordinary filenames. */
static bool
lla_option(const char *arg)
{
    static const char *const names[] = {
        "--json", "--ndjson", "--csv", "--pretty", "--search",
        "--search-context", "--search-pipe", "--fuzzy", "--timeline",
        "--table", "--grid", "--grid-ignore", "--sizemap",
        "--filter", "--preset", "--refine", "--sort-natural",
        "--sort-case-sensitive", "--sort-dirs-first", "--dirs-only",
        "--files-only", "--symlinks-only", "--no-dirs", "--no-files",
        "--no-symlinks", "--dotfiles-only", "--no-dotfiles",
        "--include-dirs", "--permission-format", "--relative-dates",
        "--date-format", "--respect-gitignore", "--no-gitignore",
        "--created", "--modified", "--allocated-size", "--extended",
        "--mounts", "--enable-plugin", "--disable-plugin",
        "--plugins-dir", "--sort-reverse", "--no-color",
        "--no-icons", "--show-symlinks", "--no-symlink-target",
        "--case-sensitive"
    };
    for (size_t i = 0; i < sizeof names / sizeof names[0]; ++i)
        if (starts_option(arg, names[i]))
            return true;
    return false;
}

/* GNU is preserved through dpkg-divert when installed system-wide.
 * The 'ls' entrypoint ignores LEAN_LS_GNU_LS and all enhanced flags. */
static const char *
gnu_ls(bool system_entry)
{
    if (!system_entry) {
        const char *override = getenv("LEAN_LS_GNU_LS");
        if (override != NULL && override[0] != '\0')
            return override;
    }
    if (access("/usr/bin/ls.lean-ls-original", X_OK) == 0)
        return "/usr/bin/ls.lean-ls-original";
    if (access("/usr/bin/ls", X_OK) == 0)
        return "/usr/bin/ls";
    return "/bin/ls";
}

/* Reject explicit engine paths that resolve to lean-ls itself. On Linux this
 * avoids infinite exec recursion if ls or lla was symlinked to lean-ls. */
static bool
is_self(const char *program)
{
#ifdef __linux__
    struct stat self;
    struct stat target;
    return stat("/proc/self/exe", &self) == 0
        && stat(program, &target) == 0
        && self.st_dev == target.st_dev && self.st_ino == target.st_ino;
#else
    (void)program;
    return false;
#endif
}

static void
run_external(const char *program, bool search_path,
             int argc, char **argv, int discard, const char *arg0)
{
    if (is_self(program)) {
        fprintf(stderr, "lean-ls: engine %s resolves to lean-ls itself\n", program);
        exit(126);
    }
    char **args = calloc((size_t)argc + 1, sizeof *args);
    if (args == NULL) {
        fputs("lean-ls: allocation failed\n", stderr);
        exit(1);
    }
    int j = 0;
    args[j++] = (char *)arg0;
    for (int i = 1; i < argc; ++i)
        if (i != discard)
            args[j++] = argv[i];
    args[j] = NULL;

    if (search_path)
        execvp(program, args);
    else
        execv(program, args);
    int saved = errno;
    fprintf(stderr, "lean-ls: cannot execute %s: %s\n", program,
            strerror(saved));
    free(args);
    exit(saved == ENOENT ? 127 : 126);
}

/* AT_EXECFN records the actual execve path, even when callers replace
 * argv[0] (e.g. `exec -a different-name /usr/bin/ls`). */
static bool
was_invoked_as_ls(const char *arg0)
{
    const char *base = strrchr(arg0, '/');
    base = base == NULL ? arg0 : base + 1;
    if (strcmp(base, "ls") == 0)
        return true;
#ifdef __linux__
    const char *execfn = (const char *)getauxval(AT_EXECFN);
    if (execfn != NULL) {
        const char *name = strrchr(execfn, '/');
        name = name == NULL ? execfn : name + 1;
        if (strcmp(name, "ls") == 0)
            return true;
    }
#endif
    return false;
}

int
lean_ls_dispatch(int argc, char **argv)
{
    /* Keep the vendored liszt/lz binaries and their test contracts intact. */
    const char *base = strrchr(argv[0], '/');
    base = base == NULL ? argv[0] : base + 1;
    if (strcmp(base, "liszt") == 0 || strcmp(base, "lz") == 0)
        return 0;
    if (was_invoked_as_ls(argv[0])) {
        const char *program = gnu_ls(true);
        if (is_self(program)) {
            fputs("lean-ls: original GNU ls missing; restore using uninstall.sh\n", stderr);
            exit(126);
        }
        /* No allocator or argument changes: preserve GNU stdout/stderr/status. */
        execv(program, argv);
        int saved = errno;
        fprintf(stderr, "lean-ls: cannot execute original GNU ls: %s\n", strerror(saved));
        exit(saved == ENOENT ? 127 : 126);
    }

    enum mode selected = MODE_NATIVE;
    int discard = -1;
    bool strict = false;
    bool lla = false;
    bool show_version = false;
    bool show_help = false;
    bool gnu_version_or_help = false;

    for (int i = 1; i < argc; ++i) {
        const char *arg = argv[i];
        if (strcmp(arg, "--") == 0)
            break;
        if (strcmp(arg, "--lean-strict") == 0) {
            strict = true;
            if (discard < 0)
                discard = i;
        } else if (strcmp(arg, "--lla") == 0) {
            lla = true;
            if (discard < 0)
                discard = i;
        } else if (strcmp(arg, "--lean-version") == 0) {
            show_version = true;
        } else if (strcmp(arg, "--lean-help") == 0) {
            show_help = true;
        } else if (strcmp(arg, "--help") == 0
                   || strcmp(arg, "--version") == 0) {
            gnu_version_or_help = true;
        } else if (lla_option(arg)) {
            lla = true;
        }
    }
    if (strict && lla) {
        fputs("lean-ls: --lean-strict conflicts with lla mode\n", stderr);
        return 2;
    }
    if (show_version) {
        puts("lean-ls 0.2.4 (GNU ls default, liszt fast mode, optional lla)");
        exit(0);
    }
    if (show_help) {
        puts("lean-ls: exact GNU ls when invoked as 'ls'; fast listing when invoked as 'lean-ls'\n"
             "  ls [GNU ls arguments]           exact system GNU output\n"
             "  lean-ls [GNU ls arguments]      fast native liszt-compatible output\n"
             "  lean-ls --lean-strict [args]    run original GNU ls exactly\n"
             "  lean-ls --lla [args]           invoke optional lla engine\n"
             "  lean-ls --json / --search      invoke optional lla engine\n"
             "  lean-ls --lean-version         show lean-ls version\n"
             "  lean-ls --lean-help            show modes\n"
             "  LEAN_LS_LLA=/path/to/lla       select lla for lean-ls modes only\n"
             "  LEAN_LS_GNU_LS=/path/to/ls    select strict engine (not for ls)\n"
             "  Native extensions: --tree --icons --git --theme");
        exit(0);
    }
    if (lla)
        selected = MODE_LLA;
    else if (strict || gnu_version_or_help)
        selected = MODE_STRICT;

    if (selected == MODE_LLA) {
        const char *program = getenv("LEAN_LS_LLA");
        if (program != NULL && program[0] != '\0')
            run_external(program, true, argc, argv, discard, program);

        /* Prefer the optional, locally built lla supplied with lean-ls. */
        const char *home = getenv("HOME");
        if (home != NULL && home[0] != '\0') {
            const char suffix[] = "/.local/libexec/lean-ls/lla";
            size_t len = strlen(home) + sizeof suffix;
            char *local = malloc(len);
            if (local == NULL) {
                fputs("lean-ls: allocation failed\n", stderr);
                exit(1);
            }
            snprintf(local, len, "%s%s", home, suffix);
            if (access(local, X_OK) == 0)
                run_external(local, false, argc, argv, discard, local);
            free(local);
        }
        /* Implicit lla switches have no special argument to remove. */
        run_external("lla", true, argc, argv, discard, "lla");
    }
    if (selected == MODE_STRICT) {
        const char *program = gnu_ls(false);
        run_external(program, false, argc, argv, discard, "/usr/bin/ls");
    }
    return 0;
}
