#ifndef LEAN_LS_DISPATCH_H
#define LEAN_LS_DISPATCH_H
/* Returns zero for the native listing path; other modes replace the process. */
int lean_ls_dispatch(int argc, char **argv);
#endif
