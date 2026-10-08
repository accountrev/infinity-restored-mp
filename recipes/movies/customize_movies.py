"""Edits to the customise movies in assets/flash/customize/customize.zip.

customize.gfx (Customize_win32: the full-screen movie, used on PC for a pad player in single player)
    LT/RT (CUST_PREV_ITEM / CUST_NEXT_ITEM) flipped a page of nine items, a leftover of the PC layout
    whose items are picked with keys 1-9. Now prevItem / nextItem move the movie's own highlight one
    slot (SetInventorySlot, as the 1-9 keys do, without applying) and turn the page at the first / last
    slot, then preview the item (SelectedItemChanged); prevCategory / nextCategory (LB/RB) put the
    highlight on the section's first item, where the list's cursor already is. LT/RT play menu_prev /
    menu_next (the pause-menu cursor sounds): their own sound, ribbon_scroll, is an empty event in the PC's
    ui.fev. Its key labels exist only in the keyboard string table (Z / X pages, F1 / F2 categories, 1-9
    under the items), so a pad player saw keyboard keys: they are renamed in place to coopui_* (see the
    split movies below; for a pad: LT / RT, LB / RB, no numbers). The handlers were made with JPEXS FFDec
    (P-code of the four method bodies); the bytes below are the file and DoABC tag lengths, the renamed
    strings and the four method bodies. What the new bodies do, as FFDec decompiles the patched movie
    (class Customize_win32): prevCategory / nextCategory gain one line after HideFillerItems(),
        this.currentIndex = this.ribbonTween["iconRibbon"].GetCursorIndex();
    and prevItem / nextItem become:
        public function prevItem() : *
        {
           if(this.listIsEmpty)
           {
              return;
           }
           CallLua("PlaySound","menu_prev");
           var _loc1_:* = this.ribbonTween["iconRibbon"];
           if(this.currentIndex > 0)
           {
              this.SetInventorySlot(this.currentIndex - 1);
           }
           else
           {
              var _loc2_:* = _loc1_.GetElementAtIndex(0).id;
              _loc1_.PageDown();
              _loc1_.SetPaging();
              this.HideFillerItems();
              if(_loc1_.GetElementAtIndex(0).id != _loc2_)
              {
                 this.currentIndex = 8;
              }
              this.ToLastValidItem();
           }
           this.SelectedItemChanged(null);
        }

        public function nextItem() : *
        {
           if(this.listIsEmpty)
           {
              return;
           }
           CallLua("PlaySound","menu_next");
           var _loc1_:* = this.ribbonTween["iconRibbon"];
           while(true)
           {
              if(this.currentIndex < 8)
              {
                 var _loc2_:* = _loc1_.GetElementAtIndex(this.currentIndex + 1);
                 if(_loc2_ != null)
                 {
                    if(_loc2_.id != "")
                    {
                       this.SetInventorySlot(this.currentIndex + 1);
                       break;
                    }
                 }
              }
              _loc2_ = _loc1_.GetElementAtIndex(0).id;
              _loc1_.PageUp();
              _loc1_.SetPaging();
              this.HideFillerItems();
              if(_loc1_.GetElementAtIndex(0).id != _loc2_)
              {
                 this.currentIndex = 0;
              }
              this.ToLastValidItem();
              break;
           }
           this.SelectedItemChanged(null);
        }

customize_h.gfx / customize_v.gfx (Customize_H / _V: the split-screen movies, from the 360)
    The item and category arrows are labelled with gameplay strings (button_target_mode, button_throw,
    button_left, button_right): LT / RT / LB / RB in the pad string table, but Left Shift / right mouse /
    Z / X in the keyboard one, while the editor keys are Z / X (items) and V / B (categories). The four
    label ids are renamed in place (same length) to coopui_*; the exe resolves those to the editor keys
    for keyboard and to the original strings for a pad (coop.c, coop_text_lookup_hook).
"""
import hashlib

# entry -> (sha256 before, sha256 after, [(offset in the original, original bytes, new bytes)])
EDITS = {
    "customize.gfx": (
        "546cd40d1919b6b047ded5eb60b8c3873b86c17b1be86f0c5abc88de2586d664",
        "34aa59fa0f984a42c36204baf4ddb8f323cc8cb56cfaadb13d55152bb279a7c6",
        [
            (4, "36c10100", "ecc10100"),
            (2377, b"@button_pageUp".hex(), b"@coopui_pageUp".hex()),
            (2647, b"@button_pageDown".hex(), b"@coopui_pageDown".hex()),
            (4286, b"@next_ribbon_category".hex(), b"@coopui_next_category".hex()),
            (4502, b"@prev_ribbon_category".hex(), b"@coopui_prev_category".hex()),
            (11493, "04920100", "ba920100"),
            (31488, b"_cbi_win32_key1".hex(), b"coopui_itemkey1".hex()),
            (31504, b"_cbi_win32_key2".hex(), b"coopui_itemkey2".hex()),
            (31520, b"_cbi_win32_key3".hex(), b"coopui_itemkey3".hex()),
            (31536, b"_cbi_win32_key4".hex(), b"coopui_itemkey4".hex()),
            (31552, b"_cbi_win32_key5".hex(), b"coopui_itemkey5".hex()),
            (31568, b"_cbi_win32_key6".hex(), b"coopui_itemkey6".hex()),
            (31584, b"_cbi_win32_key7".hex(), b"coopui_itemkey7".hex()),
            (31600, b"_cbi_win32_key8".hex(), b"coopui_itemkey8".hex()),
            (31616, b"_cbi_win32_key9".hex(), b"coopui_itemkey9".hex()),
            (84867, "39d0305d015dac022c920c46ac020146010112230000d024004fd70301d04fd803005dac022cc80b"
                "2c930c4fac0202d04fed0300d04fee0300470000ac0303010c0d39d0305d015dac022c920c46ac02"
                "0146010112230000d024014fd70301d04fd803005dac022cc80b2c940c4fac0202d04fed0300d04f"
                "ee0300470000ad0303010c0d3bd0305dac022cc80b2c950c4fac0202d02668c103d0669b032cc402"
                "66fe0a4fb00b00d0669b032cc40266fe0a4f970b00d04fed0300d04fee0300470000ae0303010c0d"
                "3bd0305dac022cc80b2c950c4fac0202d02668c103d0669b032cc40266fe0a4fb10b00d0669b032c"
                "c40266fe0a4f970b00d04fed0300d04fee0300",
                "4bd0305d015dac022c920c46ac020146010112350000d024004fd70301d04fd803005dac022cc80b"
                "2c930c4fac0202d04fed0300d0d0669b032cc40266fe0a46db040068bd03d04fee0300470000ac03"
                "03010c0d4bd0305d015dac022c920c46ac020146010112350000d024014fd70301d04fd803005dac"
                "022cc80b2c940c4fac0202d04fed0300d0d0669b032cc40266fe0a46db040068bd03d04fee030047"
                "0000ad0303030c0d76d030d066b90312010000475dac022cc80b2cdb0c4fac0202d0669b032cc402"
                "66fe0ad5d066bd0324000e0e0000d0d066bd03934fec030110340000d12400469c0b01669701d6d1"
                "4fb00b00d14f970b00d04fed0300d12400469c0b01669701d213060000d0240868bd03d04fee0300"
                "d0204fdc0301470000ae0303030c0d9101d030d066b90312010000475dac022cc80b2cd70c4fac02"
                "02d0669b032cc40266fe0ad5d066bd0324080c290000d1d066bd0391469c0b01d6d22013180000d2"
                "6697012c01130e0000d0d066bd03914fec030110340000d12400469c0b01669701d6d14fb10b00d1"
                "4f970b00d04fed0300d12400469c0b01669701d213060000d0240068bd03d04fee0300d0204fdc03"
                "01"),
        ],
    ),
    "customize_h.gfx": (
        "ae583c0f0af5b1f7b689e7b78f45e09f50301bcd96a2c6e8c7b4a3973f28824e",
        "ef650b037408bb4c0bb54ffdd00b205c2bdbe395aa0d45b64eecf4ab65a142cc",
        [
            (28694, b"@button_left".hex(), b"@coopui_left".hex()),
            (28707, b"@button_right".hex(), b"@coopui_right".hex()),
            (28723, b"@button_target_mode".hex(), b"@coopui_target_mode".hex()),
            (28837, b"@button_throw".hex(), b"@coopui_throw".hex()),
        ],
    ),
    "customize_v.gfx": (
        "3f0815cd48c58657557c4b22473389226c4b614cf0392d0f4cc3450ed0ffc9a6",
        "e3b2918334679a2a53799f30d15efad863b584fba632b740494b7cfe693cccf6",
        [
            (28667, b"@button_left".hex(), b"@coopui_left".hex()),
            (28680, b"@button_right".hex(), b"@coopui_right".hex()),
            (28696, b"@button_target_mode".hex(), b"@coopui_target_mode".hex()),
            (28810, b"@button_throw".hex(), b"@coopui_throw".hex()),
        ],
    ),
}


def build(name, data):
    """The edited movie; asserts the original and the result are exactly the known files."""
    before, after, edits = EDITS[name]
    assert hashlib.sha256(data).hexdigest() == before, f"{name}: unexpected original"
    out = bytearray(data)
    for off, old, new in sorted(edits, reverse=True):       # from the end: offsets stay valid
        old, new = bytes.fromhex(old), bytes.fromhex(new)
        assert data[off:off + len(old)] == old, f"{name}: unexpected bytes at {off}"
        out[off:off + len(old)] = new
    assert hashlib.sha256(out).hexdigest() == after, f"{name}: unexpected result"
    return bytes(out)
