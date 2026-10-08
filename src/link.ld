/* Everything goes into one blob that patch_exe.py appends as the ".coop" section.
   COOP_BASE (VA) is passed on the ld.lld command line by build.sh / build.bat. */
ENTRY(coop_poll_hook)
SECTIONS
{
  . = COOP_BASE;
  .coop : {
    *(.text .text.*)
    *(.rodata .rodata.*)
    *(.data .data.*)
    *(.bss .bss.*)
    *(COMMON)
  }
  /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) *(.debug*) }
}
