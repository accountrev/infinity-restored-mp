#!/bin/sh
# Builds build/coop.bin (raw code blob) + build/coop.sym (symbol addresses) for patch_exe.py.
# Needs only LLVM: clang, ld.lld, llvm-objcopy, llvm-nm (no Windows toolchain). build.bat does the same on Windows,
# with the same tools, so both give the same bytes.
set -e
cd "$(dirname "$0")"
mkdir -p build

# New section goes right after the last one: image base 0x400000 + SizeOfImage 0x1511000.
COOP_BASE=0x1911000

clang -target i686-unknown-linux-gnu -m32 -O2 -std=c11 \
      -ffreestanding -fno-builtin -nostdlib -fno-pic -fno-pie \
      -fno-stack-protector -fno-asynchronous-unwind-tables -fno-unwind-tables \
      -fcf-protection=none -mno-sse -mno-mmx -mstack-alignment=4 \
      -Wall -Wextra -Wno-unused-parameter \
      -c src/coop.c -o build/coop.o

# the one section is code and data together (RWX), as the PE section is
ld.lld -m elf_i386 --defsym=COOP_BASE=$COOP_BASE -T src/link.ld -o build/coop.elf build/coop.o
llvm-objcopy -O binary -j .coop build/coop.elf build/coop.bin
llvm-nm build/coop.elf | awk '$2 ~ /^[Tt]$/ {print $3, $1}' > build/coop.sym
echo "COOP_BASE $COOP_BASE" >> build/coop.sym

# sanity: nothing may reference outside the blob except fixed game addresses
if llvm-nm -u build/coop.elf | grep -q .; then echo "undefined symbols:"; llvm-nm -u build/coop.elf; exit 1; fi
echo "built build/coop.bin ($(stat -c %s build/coop.bin) bytes)"
cat build/coop.sym
