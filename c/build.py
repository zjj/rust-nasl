#!/usr/bin/env python3
#coding: utf8

import os
import sys
import argparse
import subprocess


def get_cflags():
    cflags = []
    cmds = [
        "pkg-config --cflags glib-2.0",
        "pkg-config --cflags gio-2.0",
        "ksba-config --cflags",
        "pcap-config --cflags",
        "gpgme-config --cflags",
        "libgcrypt-config --cflags",
        "pkg-config --cflags hiredis",
        "pkg-config --cflags uuid",
    ]

    for cmd in cmds:
        cflag = subprocess.run(cmd, stdout=subprocess.PIPE, check=True, shell=True).stdout.decode("utf-8")
        cflags.append(cflag.replace("\n", ""))

    return " ".join(cflags) + " -I./"

def get_libs():
    clibs = []
    cmds = [
        "pkg-config --libs glib-2.0",
        "pkg-config --libs gio-2.0",
        "pkg-config --libs gnutls",
        "ksba-config --libs",
        "pcap-config --libs",
        "gpgme-config --libs",
        "libgcrypt-config --libs",
        "pkg-config --libs hiredis",
        "pkg-config --libs uuid",
    ]

    for cmd in cmds:
        clib = subprocess.run(cmd, stdout=subprocess.PIPE, check=True, shell=True).stdout.decode("utf-8")
        clibs.append(clib.replace("\n", ""))

    return " ".join(clibs) + " -lssh -lpcre -lm -lz "


def build_grammar():
    assert(os.path.exists("./nasl/nasl_grammar.y"))

    c_file = os.path.exists("./nasl/nasl_grammar.tab.c")
    c_header = os.path.exists("./nasl/nasl_grammar.tab.h")
    c_output = os.path.exists("./nasl/nasl_grammar.output")

    if not c_file or not c_header or not c_output:
        cmd = "cd nasl && bison -d -v -t -p nasl ./nasl_grammar.y"
        print(cmd)
        subprocess.run(cmd, stdout=subprocess.PIPE, check=True, shell=True).stdout.decode("utf-8")

    assert(os.path.exists("./nasl/nasl_grammar.tab.c"))
    assert(os.path.exists("./nasl/nasl_grammar.tab.h"))
    assert(os.path.exists("./nasl/nasl_grammar.output"))


def build():
    build_grammar()

    cflags = get_cflags()
    clibs = get_libs()

    # HAVE_LIBKSBA  nasl_cert.c
    # HAVE_NETSNMP  nasl_snmp.c
    # NASL_DEBUG
    configs = "-D OPENVASSD_CONF=\"\\\"./\\\"\""
    configs += " -D GVM_PID_DIR=\"\\\"./\\\"\""
    configs += " -D OPENVAS_SYSCONF_DIR=\"\\\"./\\\"\""
    configs += " -D GVM_SYSCONF_DIR=\"\\\"./\\\"\""
    configs += " -D OPENVAS_NASL_VERSION=\"\\\"5.06\\\"\""
    configs += " -D OPENVASLIB_VERSION=\"\\\"5.06\\\"\""
    
    c_files = set()
    objs = set()
    headers = set()

    for project in ("base", "util", "misc", "nasl"):
        files = os.listdir(project)
        for filename in files:
            filename = "%s/%s" % ( project, filename )
            
            if "nasl-lint.c" in filename:
                continue
            if "nasl.c" in filename:
                continue

            if filename.endswith(".c"):
                objectname = filename[:-2] + ".o"
                if not os.path.exists(objectname):
                    cmd = "clang -fPIC %s %s -c %s -o %s" % (cflags, configs, filename, objectname,)
                    print(cmd)
                    subprocess.run(cmd, stdout=subprocess.PIPE, check=True, shell=True).stdout.decode("utf-8")
                objs.add(objectname)
                c_files.add(filename)
            elif filename.endswith(".h"):
                headers.add(filename)

    objs = list(objs)
    headers = list(headers)
    c_files = list(c_files)

    header_wrap = ""
    for h in headers:
        header_wrap += "#include \"%s\"\n" % h
    open("libnasl.h", "w").write(header_wrap)

    cmd = "ar -rcsv libnasl.a %s" % " ".join(objs)
    print(cmd)
    subprocess.run(cmd, stdout=subprocess.PIPE, check=True, shell=True).stdout.decode("utf-8")
    
    if sys.platform == "darwin":
        cmd = "clang -fPIC %s %s %s libnasl.a nasl/nasl.c -o nasli" % ( cflags, clibs, configs, )
    elif sys.platform == "linux":
        cmd = "clang -fPIC %s %s %s %s nasl/nasl.c -o nasli" % ( cflags, clibs, configs, " ".join(objs), )
    print(cmd)
    subprocess.run(cmd, stdout=subprocess.PIPE, check=True, shell=True).stdout.decode("utf-8")

    if sys.platform == "darwin":
        cmd = "clang -shared -fPIC %s %s %s libnasl.a nasl/nasl.c -o libnasl.dylib" % ( cflags, clibs, configs, )
    elif sys.platform == "linux":
        cmd = "clang -shared -fPIC %s %s %s %s nasl/nasl.c -o libnasl.so" % ( cflags, clibs, configs, " ".join(objs))
    print(cmd)
    subprocess.run(cmd, stdout=subprocess.PIPE, check=True, shell=True).stdout.decode("utf-8")


def check():
    import ctypes

    if sys.platform == "darwin":
        libname = "./libnasl.dylib"
    elif sys.platform == "linux":
        libname = "./libnasl.so"

    dll = ctypes.cdll.LoadLibrary(libname)
    print("\n@Tests:")
    print("nasl_version: ", dll.nasl_version())
    

def clear():
    for project in ("base", "util", "misc", "nasl"):
        files = os.listdir(project)
        for filename in files:
            filename = "%s/%s" % ( project, filename )

            if filename.endswith(".o") or filename.endswith(".gch"):
                os.remove(filename)

    os.remove("./nasli")
    os.remove("./libnasl.h")
    os.remove("./libnasl.a")

    if sys.platform == "darwin":
        os.remove("./libnasl.dylib")
    elif sys.platform == "linux":
        os.remove("./libnasl.so")


def main():
    parser = argparse.ArgumentParser(description='build script')
    parser.add_argument('mode', type=str, help="enum('build', 'clear')")

    args = parser.parse_args()

    if args.mode == "build":
        build()
        check()
    elif args.mode == "clear":
        try:
            clear()
        except:
            pass

if __name__ == '__main__':
    main()
