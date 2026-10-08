@echo off
rem Builds build\coop.bin (raw code blob) + build\coop.sym (symbol addresses) for patcher\patch_exe.py: the
rem Windows version of build.sh, with the same tools, so both give the same bytes. Needs LLVM for Windows (clang,
rem ld.lld, llvm-objcopy, llvm-nm on the PATH).
setlocal
cd /d "%~dp0"
if not exist build mkdir build

rem New section goes right after the last one: image base 0x400000 + SizeOfImage 0x1511000.
set COOP_BASE=0x1911000

clang -target i686-unknown-linux-gnu -m32 -O2 -std=c11 ^
      -ffreestanding -fno-builtin -nostdlib -fno-pic -fno-pie ^
      -fno-stack-protector -fno-asynchronous-unwind-tables -fno-unwind-tables ^
      -fcf-protection=none -mno-sse -mno-mmx -mstack-alignment=4 ^
      -Wall -Wextra -Wno-unused-parameter ^
      -c src/coop.c -o build/coop.o || exit /b 1

rem the one section is code and data together (RWX), as the PE section is
ld.lld -m elf_i386 --defsym=COOP_BASE=%COOP_BASE% -T src/link.ld -o build/coop.elf build/coop.o || exit /b 1
llvm-objcopy -O binary -j .coop build/coop.elf build/coop.bin || exit /b 1
(for /f "tokens=1-3" %%a in ('llvm-nm build/coop.elf') do @if /i "%%b"=="T" echo %%c %%a) > build\coop.sym
>> build\coop.sym echo COOP_BASE %COOP_BASE%

rem sanity: nothing may reference outside the blob except fixed game addresses
set UNDEFINED=
for /f "delims=" %%u in ('llvm-nm -u build/coop.elf') do (
    echo undefined symbol: %%u
    set UNDEFINED=1
)
if defined UNDEFINED exit /b 1
for %%f in (build\coop.bin) do echo built build\coop.bin (%%~zf bytes)
type build\coop.sym
