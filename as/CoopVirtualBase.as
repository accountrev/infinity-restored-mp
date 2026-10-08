package
{
   import ava.*;
   import flash.display.DisplayObject;
   import flash.display.Loader;
   import flash.display.MovieClip;
   import flash.events.Event;
   import flash.net.URLRequest;

   // Co-op patch: the Virtual Base for two players (recipes/movies/vr_movie.py).
   // vr_movie.py places one of these on the reader's root clip (VirtualReader_win32), whose own code is left
   // as the game ships it. This works from the root's public members and follows its state every frame:
   //  - on the Figures tab the character ribbon is split in two halves of three characters, P1 left and P2
   //    right (the Discs tab keeps the stock ribbon); two more copies of the ribbon give the middle endcaps
   //    and arrows, the right one holds P2's list;
   //  - the info bar stays P1's figure; the name banners are copies behind the Base art; P2's figure is a copy
   //    moved by P2's texel offset (Lua CoopLayout).
   // Ribbon units: mc_ribbon's own coordinates, the screen spans about +-512.
   public class CoopVirtualBase extends MovieClip
   {

      internal var vr:* = null;

      internal var started:Boolean = false;

      internal var half:Number = 255.7;

      internal var innerShift:Number = 511.4;

      internal var listX:Number = 15;

      internal var slotX:Number = 14.6;

      internal var slotStep:Number = 194.15;

      // the list's slot positions (its template slots b0-b8; b0 and b8 are the off-screen ends)
      internal var slots:Array = [-950,-567.9,-373.75,-179.6,14.6,208.75,402.9,597.05,950];

      internal var p1:int = -2;

      internal var p2:int = -1;

      internal var split:Boolean = true;

      internal var p1Inner:MovieClip = null;

      internal var p2Ribbon:MovieClip = null;

      internal var p1Banner:MovieClip = null;

      internal var p2Banner:MovieClip = null;

      internal var p2Figure:MovieClip = null;

      internal var p2Character:String = null;

      internal var p2Pick:String = "";

      internal var p2Active:Boolean = true;

      internal var discsAbove:DisplayObject = null;

      internal var discsBehind:int = -1;

      public function CoopVirtualBase()
      {
         super();
         addEventListener(Event.ENTER_FRAME,this.Tick);
         addEventListener(Event.FRAME_CONSTRUCTED,this.Tick);
         addEventListener(Event.EXIT_FRAME,this.Tick);
      }

      internal function Tick(e:Event) : void
      {
         if(!this.started)
         {
            // the game runs the reader's Init right after giving the movie its Lua name
            this.vr = parent;
            if(this.vr == null || this.vr.luaName == "this")
            {
               return;
            }
            this.Start();
         }
         this.Layout();
      }

      internal function Start() : void
      {
         var players:Array = ("" + this.vr.CallLua("CoopPlayers")).split(",");
         var layout:Array = ("" + this.vr.CallLua("CoopLayout")).split(",");
         var bar:MovieClip = this.vr.characterInfoBar;
         var base:DisplayObject = this.vr.getChildAt(this.vr.getChildIndex(bar) - 1);
         var list:* = null;
         this.started = true;
         this.discsAbove = this.vr.getChildAt(this.vr.getChildIndex(this.vr.hexCoinScreen) + 1);
         this.vr.mc_ribbon.avaList.addEventListener(AvaEvent.LIST_ITEM_SCROLLED_IN,this.ListScrolled);
         this.vr.mc_ribbon.avaList.addEventListener(AvaEvent.LIST_CREATED,this.ListRebuilt);
         this.p2 = int(players[1]);
         if(this.p2 >= 0)
         {
            this.p1 = int(players[0]);
            this.vr.FixUp(this.vr,this.vr.mc_ribbon.avaList,this.vr.luaName,this.p1,this.vr.test);
         }
         this.p1Inner = this.Ribbon(-this.innerShift,["right_endcap","right_arrow"]);
         this.p2Ribbon = this.Ribbon(this.innerShift,["left_endcap","left_arrow","avaList"]);
         this.InertList(this.p1Inner.avaList);
         list = this.p2Ribbon.avaList;
         if(this.p2 >= 0)
         {
            this.vr.FixUp(this.vr,list,this.vr.luaName,this.p2,this.vr.test);
            list.selectedItemSetter = "";
            list.startIDGetter = "GetStartIDP2";
            list.useTouchScrolling = false;
            list.disableMouseWheelScrolling = true;
            list.addEventListener(AvaEvent.LIST_CREATED,this.P2ListBuilt);
            list.addEventListener(AvaSelectedEvent.SELECTED_ITEM_CHANGED,this.P2ItemChanged);
            list.addEventListener(AvaSelectedEvent.SELECTED,this.P2Picked);
            list.addEventListener(AvaEvent.LIST_ITEM_SCROLLED_IN,this.ListScrolled);
            list.addEventListener(AvaEvent.LIST_CREATED,this.ListRebuilt);
            this.p2Pick = "" + this.vr.CallLua("CoopP2Character");
            this.p2Ribbon.left_arrow.addEventListener(AvaEvent.BUTTON_CLICKED,this.P2Previous);
            this.vr.mc_ribbon.right_arrow.addEventListener(AvaEvent.BUTTON_CLICKED,this.P2Next);
            this.vr.mc_ribbon.avaList.addEventListener(AvaEvent.LIST_CREATED,this.P1ListBuilt);
         }
         else
         {
            this.InertList(list);
         }
         // banners behind the Base art (the root's child just below the info bar), P2's below P1's
         this.p1Banner = this.InfoBar(0,0,this.vr.getChildIndex(base));
         this.p2Banner = this.InfoBar(0,Number(layout[2]),this.vr.getChildIndex(base));
         this.p2Figure = this.InfoBar(Number(layout[0]),Number(layout[1]),this.vr.getChildIndex(bar) + 1);
         this.Parts(this.p2Figure,false);
         this.Parts(this.p1Banner,true);
         this.Parts(this.p2Banner,true);
      }

      internal function Ribbon(shift:Number, keep:Array) : MovieClip
      {
         // a copy of the ribbon, shifted so its stock endcap lands in the middle; only `keep` shows
         var r:MovieClip = new mc_ribbon();
         var i:int = 0;
         r.transform.matrix = this.vr.mc_ribbon.transform.matrix;
         r.x += shift * this.vr.mc_ribbon.scaleX;
         for(i = 0; i < r.numChildren; i++)
         {
            if(keep.indexOf(r.getChildAt(i).name) < 0)
            {
               r.getChildAt(i).visible = false;
            }
         }
         this.vr.FixUp(this.vr,r,this.vr.luaName,-2,this.vr.test);
         this.vr.FixUp2(this.vr,r,{
            "platform":this.vr.platform,
            "touch_screen":this.vr.touch_screen
         });
         r.visible = false;
         this.vr.addChildAt(r,this.vr.getChildIndex(this.vr.mc_ribbon) + 1);
         return r;
      }

      internal function InertList(list:*) : void
      {
         // a ribbon copy's unused list: no items, no input (there is no player 99), hidden
         this.vr.FixUp(this.vr,list,this.vr.luaName,99,this.vr.test);
         list.UIDSGetter = "CoopNoItems";
         list.startIDGetter = "CoopNoItems";
         list.useTouchScrolling = false;
         list.disableMouseWheelScrolling = true;
         list.visible = false;
      }

      internal function InfoBar(dx:Number, dy:Number, index:int) : MovieClip
      {
         var b:MovieClip = new characterInfoBar();
         b.transform.matrix = this.vr.characterInfoBar.transform.matrix;
         b.x += dx;
         b.y += dy;
         b.visible = false;
         this.vr.addChildAt(b,index);
         return b;
      }

      internal function Parts(b:MovieClip, banner:Boolean) : void
      {
         // hides the other part of an info bar. Banner: the blue bar (depth 1, the first child) and the two
         // names; the rest is the figure (swap flash, render, glow).
         var i:int = 0;
         var c:DisplayObject = null;
         for(i = 0; i < b.numChildren; i++)
         {
            c = b.getChildAt(i);
            if((i == 0 || c == b.characterName || c == b.characterShow) != banner)
            {
               c.visible = false;
            }
         }
      }

      internal function Layout() : void
      {
         var rib:MovieClip = this.vr.mc_ribbon;
         var bar:MovieClip = this.vr.characterInfoBar;
         var split:Boolean = this.vr.hexCoinScreen.currentLabel != "HexMode";
         var p2:Boolean = this.p2 >= 0;
         var on:Boolean = Boolean(rib.left_arrow.visible);
         if(split != this.split)
         {
            this.split = split;
            if(this.p2Character != null)
            {
               this.Alpha(this.p2Figure,this.p2Banner,this.p2Character);
            }
         }
         // the Disc images stand on the Base's hexagon, behind the figures (Figures tab); on the Discs tab the
         // Disc screen (its info tabs) stays above them, as in the game
         if(int(split) != this.discsBehind)
         {
            this.discsBehind = int(split);
            this.PutBelow(this.vr.hexCoinScreen,split ? bar : this.discsAbove);
         }
         // P1: the stock list moved to its half, three slots shown (Discs tab: stock)
         this.PlaceList(rib,split ? this.listX - this.half : this.listX);
         this.ShowThree(rib.avaList,split);
         this.P1Outlines();
         // the stock right endcap and arrow are P2's outer ones while split (hidden without P2)
         rib.right_endcap.visible = on && (p2 || !split);
         rib.right_arrow.visible = on && (p2 || !split);
         rib.right_arrow.clickedSetter = split ? "" : "NextItem";
         this.Follow(this.p1Inner,rib,split);
         this.p1Inner.right_endcap.visible = on;
         this.p1Inner.right_arrow.visible = on;
         this.Follow(this.p2Ribbon,rib,split && p2);
         if(p2)
         {
            this.p2Ribbon.left_endcap.visible = on;
            this.p2Ribbon.left_arrow.visible = on;
            this.p2Ribbon.left_arrow.clickedSetter = "";
            this.p2Ribbon.avaList.visible = rib.avaList.visible;
            // P2's list takes input on the Figures tab while P1's ribbon is enabled (set on change only: the list
            // turns itself off while it scrolls)
            if((split && on) != this.p2Active)
            {
               this.p2Active = split && on;
               this.p2Ribbon.avaList.SetActive(this.p2Active);
            }
            this.PlaceList(this.p2Ribbon,this.listX - this.half);
            this.ShowThree(this.p2Ribbon.avaList,true);
            this.P2Outlines();
         }
         // P1's banner follows the info bar, whose own banner parts stay hidden
         this.Parts(bar,false);
         this.p1Banner.visible = bar.visible;
         this.p1Banner.alpha = bar.alpha;
         if(this.p1Banner.currentFrame != bar.currentFrame)
         {
            this.p1Banner.gotoAndStop(bar.currentFrame);
         }
         if(this.p1Banner.characterName.textField.text != bar.characterName.textField.text)
         {
            this.p1Banner.characterName.textField.text = bar.characterName.textField.text;
         }
         if(this.p1Banner.characterShow.textField.text != bar.characterShow.textField.text)
         {
            this.p1Banner.characterShow.textField.text = bar.characterShow.textField.text;
         }
         this.p1Banner.characterName.visible = split;
         this.p1Banner.characterShow.visible = split;
         // P2's figure and banner hide with P1's (closing)
         if(this.p2Figure.visible && bar.currentFrame >= 45 && this.p2Figure.currentFrame < 45)
         {
            this.HideP2();
         }
      }

      internal function Follow(copy:MovieClip, rib:MovieClip, show:Boolean) : void
      {
         // a ribbon copy plays the ribbon's fade with it
         copy.visible = rib.visible && show;
         if(copy.currentFrame != rib.currentFrame)
         {
            copy.gotoAndStop(rib.currentFrame);
         }
      }

      internal function PlaceList(ribbon:MovieClip, x:Number) : void
      {
         // Once moved from script the list no longer follows the ribbon's timeline, so its fade (the ribbon's
         // frames 18-19 in, 27-30 out) is redone here.
         var f:int = ribbon.currentFrame;
         var list:* = ribbon.avaList;
         list.x = x;
         if(f < 2)
         {
            list.alpha = 1;
         }
         else if(f < 18)
         {
            list.alpha = 0;
         }
         else if(f == 18)
         {
            list.alpha = 85 / 256;
         }
         else if(f == 19)
         {
            list.alpha = 171 / 256;
         }
         else if(f < 27)
         {
            list.alpha = 1;
         }
         else if(f < 31)
         {
            list.alpha = (256 - 51 * (f - 26)) / 256;
         }
         else
         {
            list.alpha = 0;
         }
      }

      internal function ShowThree(list:*, split:Boolean) : void
      {
         // Only the three middle slots show and take clicks, by position: with a fixed cursor the list moves its
         // slot objects round as it scrolls. A slot shows when it is in the middle three and so is where it is
         // going (coopTarget, from ListScrolled), so one leaving is hidden before it moves out. Not a mask: with
         // masks, the slots' character icons didn't draw.
         var i:int = 0;
         var c:* = null;
         var t:Number = NaN;
         for(i = 0; i < list.numChildren; i++)
         {
            c = list.getChildAt(i);
            if(c is AvaElement)
            {
               t = Number(c.coopTarget);
               if(!isNaN(t) && Math.abs(c.x - t) < 0.5)
               {
                  c.coopTarget = NaN;
                  t = NaN;
               }
               c.visible = !split || this.Middle(c.x) && (isNaN(t) || this.Middle(t));
               c.mouseEnabled = c.visible;
            }
         }
      }

      internal function Middle(x:Number) : Boolean
      {
         return Math.abs(x - this.slotX) < 1.5 * this.slotStep;
      }

      internal function SlotOf(x:Number) : int
      {
         var i:int = 0;
         var best:int = 0;
         for(i = 1; i < this.slots.length; i++)
         {
            if(Math.abs(x - this.slots[i]) < Math.abs(x - this.slots[best]))
            {
               best = i;
            }
         }
         return best;
      }

      internal function ListScrolled(e:AvaEvent) : void
      {
         // A list scrolled by one: its slot objects will move one slot (their tweens run later), `e.element` is
         // the end one coming in, and a new end slot object stands at the far end already.
         var list:* = e.currentTarget;
         var moved:* = e.element;
         var dir:int = moved.x > this.slotX ? 1 : -1;
         var edge:int = dir > 0 ? this.slots.length - 1 : 0;
         var i:int = 0;
         var c:* = null;
         var s:int = 0;
         for(i = 0; i < list.numChildren; i++)
         {
            c = list.getChildAt(i);
            if(c is AvaElement)
            {
               if(c == moved)
               {
                  s = edge - dir;
               }
               else if(Math.abs(c.x - this.slots[edge]) < 0.5)
               {
                  c.coopTarget = NaN;
                  continue;
               }
               else
               {
                  s = this.SlotOf(isNaN(Number(c.coopTarget)) ? c.x : Number(c.coopTarget)) - dir;
                  s = s < 0 ? 0 : (s > this.slots.length - 1 ? this.slots.length - 1 : s);
               }
               c.coopTarget = this.slots[s];
            }
         }
         this.ShowThree(list,list != this.vr.mc_ribbon.avaList || this.split);
      }

      internal function ListRebuilt(e:Event) : void
      {
         // a (re)built list places its slots without moving them
         var list:* = e.currentTarget;
         var i:int = 0;
         for(i = 0; i < list.numChildren; i++)
         {
            if(list.getChildAt(i) is AvaElement)
            {
               list.getChildAt(i).coopTarget = NaN;
            }
         }
      }

      internal function PutBelow(obj:DisplayObject, ref:DisplayObject) : void
      {
         var i:int = this.vr.getChildIndex(ref);
         this.vr.setChildIndex(obj,this.vr.getChildIndex(obj) < i ? i - 1 : i);
      }

      internal function IsOutline(l:*) : Boolean
      {
         var url:String = null;
         if(!(l is Loader))
         {
            return false;
         }
         url = "" + l.contentLoaderInfo.url;
         return url.length > 2 && url.substr(url.length - 2) == "_s";
      }

      internal function P1Outlines() : void
      {
         // The game loads a slot's outline again each time the slot's state is set, without removing the
         // earlier copies (SetState first calls ResetCharacter, which is empty in this build), so the
         // translucent glow gets brighter as the cursor moves. Only one copy is shown.
         var list:* = this.vr.mc_ribbon.avaList;
         var i:int = 0;
         var j:int = 0;
         var c:* = null;
         var l:* = null;
         var shown:Boolean = false;
         for(i = 0; i < list.numChildren; i++)
         {
            c = list.getChildAt(i);
            if(c is AvaElement && c.character_mc != null)
            {
               shown = false;
               for(j = 0; j < c.character_mc.numChildren; j++)
               {
                  l = c.character_mc.getChildAt(j);
                  if(this.IsOutline(l))
                  {
                     l.visible = !shown;
                     shown = true;
                  }
               }
            }
         }
      }

      internal function P2Outlines() : void
      {
         // A slot's selected outline (`<character>_s` over its render) is drawn for the game's
         // CharacterPicked, which is P1's pick: in P2's list it is hidden and P2's pick gets one of its own.
         var list:* = this.p2Ribbon.avaList;
         var i:int = 0;
         var j:int = 0;
         var c:* = null;
         var mc:* = null;
         var l:* = null;
         var mine:Boolean = false;
         var have:Boolean = false;
         var outline:Loader = null;
         for(i = 0; i < list.numChildren; i++)
         {
            c = list.getChildAt(i);
            if(!(c is AvaElement) || c.character_mc == null)
            {
               continue;
            }
            mc = c.character_mc;
            mine = this.p2Pick != "" && c.GetID() == this.p2Pick;
            have = false;
            j = 0;
            while(j < mc.numChildren)
            {
               l = mc.getChildAt(j);
               if(l.name.indexOf("coopOutline:") == 0)
               {
                  if(mine && l.name == "coopOutline:" + this.p2Pick && !have)
                  {
                     have = true;
                  }
                  else
                  {
                     mc.removeChild(l);
                     continue;
                  }
               }
               else if(this.IsOutline(l))
               {
                  l.visible = false;
               }
               j++;
            }
            if(mine && !have)
            {
               outline = new Loader();
               outline.name = "coopOutline:" + this.p2Pick;
               outline.x = -332;
               outline.y = -260;
               outline.contentLoaderInfo.addEventListener(Event.COMPLETE,this.OutlineLoaded);
               outline.load(new URLRequest("img://ui/virtualreadercharacters/" + this.p2Pick + "_s"));
               mc.addChild(outline);
            }
         }
      }

      internal function OutlineLoaded(e:Event) : void
      {
         // drawn at 512x512, as the game's loader (AvaLoadManager) sizes the slots' images
         var bmp:* = e.currentTarget.content;
         if(bmp != null)
         {
            bmp.smoothing = true;
            bmp.width = 512;
            bmp.height = 512;
         }
      }

      // ---- P2's list ----
      internal function P1ListBuilt(e:Event) : void
      {
         // the game rebuilt P1's list (new items, or back to the Figures tab): P2's too
         if(Boolean(this.vr.CallLua("IsCharacterMode")))
         {
            this.p2Ribbon.avaList.Rebuild();
         }
      }

      internal function P2ListBuilt(e:Event) : void
      {
         var character:String = "" + this.vr.CallLua("GetStartIDP2");
         if(Boolean(this.vr.CallLua("IsCharacterMode")))
         {
            this.p2Ribbon.avaList.GoToID(character);
            this.ShowP2(character);
         }
      }

      internal function P2ItemChanged(e:AvaSelectedEvent) : void
      {
         var id:String = "" + e.id;
         if(Boolean(this.vr.CallLua("SelectItemP2",id)))
         {
            this.ShowP2(id);
         }
      }

      internal function P2Picked(e:AvaSelectedEvent) : void
      {
         var id:String = "" + e.id;
         if(Boolean(this.vr.CallLua("PickCharacterP2",id)))
         {
            this.p2Pick = id;
            if(id != this.p2Character)
            {
               this.ShowP2(id);
            }
         }
      }

      internal function P2Previous(e:Event) : void
      {
         if(this.CanScroll())
         {
            this.p2Ribbon.avaList.PreviousElement();
         }
      }

      internal function P2Next(e:Event) : void
      {
         if(this.split && this.CanScroll())
         {
            this.p2Ribbon.avaList.NextElement();
         }
      }

      internal function CanScroll() : Boolean
      {
         return !this.vr.mc_webcodeDialog.visible && !this.vr.mc_unlockDialog.visible && Boolean(this.vr.mc_ribbon.visible);
      }

      // ---- P2's figure and banner (as the reader's ShowCharacter / HideCharacter / UpdateCharacterAlpha) ----
      internal function ShowP2(character:String) : void
      {
         var fig:MovieClip = this.p2Figure;
         var ban:MovieClip = this.p2Banner;
         var self:CoopVirtualBase = this;
         this.p2Character = character;
         if(fig.visible)
         {
            fig.gotoAndPlay("swap_character");
            ban.gotoAndPlay("swap_character");
            this.vr.loadAvatarImage(character,fig.characterContainer,"AvatarImageP2");
            this.Alpha(fig,ban,character);
         }
         else
         {
            fig.visible = true;
            ban.visible = true;
            fig.gotoAndPlay("show_character_info");
            ban.gotoAndPlay("show_character_info");
            this.vr.setTimeout(500,function():*
            {
               fig.gotoAndPlay("swap_character");
               ban.gotoAndPlay("swap_character");
               self.vr.loadAvatarImage(character,fig.characterContainer,"AvatarImageP2");
               self.Alpha(fig,ban,character);
            });
         }
         ban.characterName.textField.text = "@" + character;
         ban.characterShow.textField.text = this.vr.CallLua("GetShowName",character);
      }

      internal function HideP2() : void
      {
         var fig:MovieClip = this.p2Figure;
         var ban:MovieClip = this.p2Banner;
         fig.gotoAndPlay("hide_character_info");
         ban.gotoAndPlay("hide_character_info");
         this.vr.setTimeout(this.vr.infobarFadeTime,function():*
         {
            fig.visible = false;
            ban.visible = false;
         });
      }

      internal function Alpha(fig:MovieClip, ban:MovieClip, character:String) : void
      {
         var isCharacterMode:Boolean = Boolean(this.vr.CallLua("IsCharacterMode"));
         if(Boolean(this.vr.CallLua("CharacterLocked",character)) || !isCharacterMode)
         {
            fig.alpha = 0.5;
            ban.alpha = 0.5;
         }
         else
         {
            fig.alpha = 1;
            ban.alpha = 1;
         }
         ban.characterName.visible = isCharacterMode;
         ban.characterShow.visible = isCharacterMode;
         fig.baseGlow.visible = isCharacterMode;
      }
   }
}
