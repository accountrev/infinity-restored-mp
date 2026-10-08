-- Co-op patch: the Virtual Base for two players (recipes/movies/vr_movie.py).
-- The game's own screen script is kept in presentation.zip as virtualreader_orig.lua, unchanged; this one
-- loads it and adds player 2's half of the character selector (the movie's side: as/CoopVirtualBase.as).
--   P1 = the first local player: the left half and the Discs. P2 = the other local player: the right half.
--   Both use the screen at once: whoever opens it, the other one is paused too, and either can close it.
local VirtualReaderData = require("VirtualReaderData")
require("VirtualReader_Orig")

local defaultAvatarName = "AV_MrInc"
local COOP_LAYOUT = "@COOP_LAYOUT@"   -- filled in by patch_exe.py: P2's figure offset x,y and banner offset y

-- player 1 and player 2 (-1 without a second local player)
local function coopPlayers()
  if Players_NumLocalPlayers() < 2 then
    return 0, -1
  end
  if Players_IsPlayerFirstLocalPlayer(0) then
    return 0, 1
  end
  return 1, 0
end

-- the Virtual Base name of a player's character, from the figure it was built from (GetPlayerAvatarData's fourth
-- value, added by the co-op patch). Its avatar name is the actor's (AV_Perry, AV_Mike), not the figure's
-- Gateway (PNF_Perry, MU_Mike) the Virtual Base data is keyed by; each sku_id is one figure.
local function readerName(figure)
  if figure == nil or figure == 0 then
    return nil
  end
  for i = 1, #VirtualReaderData.SourceAvatarData do
    local data = VirtualReaderData.SourceAvatarData[i]
    if tonumber(data.sku_id) == figure then
      return data.Name
    end
  end
  return nil
end

local origOnEnter = VirtualReader.onEnter
function VirtualReader:onEnter()
  origOnEnter(self)
  local p1, p2 = coopPlayers()
  self.coopOther = nil
  self.coopClosed = nil
  self.coopP2Start = nil
  self.coopP2Picked = nil
  if p2 >= 0 then
    local other = self.InstanceData.playerNum == p1 and p2 or p1
    if not UI_IsScreenActive(other) then
      Pause_PauseGame(other, false, false)
      self.coopOther = other
    end
    local _, _, _, figure = GetPlayerAvatarData(p2)
    self.coopP2Start = readerName(figure)
  end
end

-- Player 2 dropped out with the screen open (their pad was unplugged): their screens are dumped, so only onExit
-- runs, not ExitScreen, and the other player it paused would stay paused (no pause menu for them).
local origOnExit = VirtualReader.onExit
function VirtualReader:onExit()
  origOnExit(self)
  if self.coopOther ~= nil and not self.coopClosed then
    Pause_UnPauseFromPausedScreenIfPaused(self.coopOther)
  end
end

local origExitScreen = VirtualReader.ExitScreen
function VirtualReader:ExitScreen()
  self.coopClosed = true
  local p1, p2 = coopPlayers()
  if p2 < 0 then
    return origExitScreen(self)
  end
  -- as the game's ExitScreen, with each half's pick going to its own player (the Discs are P1's)
  self:RemoveScreen()
  Pause_UnPauseFromPausedScreenIfPaused(self.InstanceData.playerNum)
  if self.coopOther ~= nil then
    Pause_UnPauseFromPausedScreenIfPaused(self.coopOther)
  end
  local picks = {{p1, self.pickedChar}}
  if self.coopP2Picked ~= nil and self.coopP2Picked ~= self.coopP2Start then
    -- one figure per character: if P1 takes P2's old character, P2 changes first
    if self.pickedChar == self.coopP2Start then
      table.insert(picks, 1, {p2, self.coopP2Picked})
    else
      table.insert(picks, {p2, self.coopP2Picked})
    end
  end
  for i = 1, #picks do
    local avatarData = self:GetAvailableAvatarData(picks[i][2])
    if avatarData ~= nil then
      Players_ChangeAvatar(picks[i][1], avatarData.Gateway, avatarData.IAP, "IGP_" .. avatarData.Gateway, avatarData.sku_id)
    end
  end
  local storedHexDataIndex = {0, 0, 0}
  for slot = 1, #self.selectedHex do
    for hexDataIndex = 1, #VirtualReaderData.SourceHexData do
      if VirtualReaderData.SourceHexData[hexDataIndex].displayName == self.selectedHex[slot] then
        storedHexDataIndex[slot] = hexDataIndex
      end
    end
  end
  if #self.selectedHex == 0 then
    Players_SetHexCoins(p1, 0)
  elseif #self.selectedHex == 1 then
    Players_SetHexCoins(p1, 1, VirtualReaderData.SourceHexData[storedHexDataIndex[1]].id)
  elseif #self.selectedHex == 2 then
    Players_SetHexCoins(p1, 2, VirtualReaderData.SourceHexData[storedHexDataIndex[1]].id, VirtualReaderData.SourceHexData[storedHexDataIndex[2]].id)
  elseif #self.selectedHex == 3 then
    Players_SetHexCoins(p1, 3, VirtualReaderData.SourceHexData[storedHexDataIndex[1]].id, VirtualReaderData.SourceHexData[storedHexDataIndex[2]].id, VirtualReaderData.SourceHexData[storedHexDataIndex[3]].id)
  end
  if UI.GetHandleFromName("FrontEndBackground", 0) ~= UI.INVALID_UI_HANDLE then
    self:CallScreenFunctionByScreenName("FrontEndBackground", 0, "ShowMenu")
  end
  if UI.GetHandleFromName("HelpBubble", -1) ~= UI.INVALID_UI_HANDLE then
    self:CallScreenFunctionByScreenName("HelpBubble", -1, "ShowAll")
  end
end

-- P1 can't take the character P2 has picked (one figure per character)
local origPickCharacter = VirtualReader.PickCharacter
function VirtualReader:PickCharacter(option)
  if self.listMode == "character" and option ~= nil and option == (self.coopP2Picked or self.coopP2Start) then
    return
  end
  return origPickCharacter(self, option)
end

-- ---- called by the movie ----
function VirtualReader:CoopPlayers()
  local p1, p2 = coopPlayers()
  return p1 .. "," .. p2
end

function VirtualReader:CoopLayout()
  return COOP_LAYOUT
end

function VirtualReader:CoopNoItems()
  return nil
end

-- P2's character for the selected outline in P2's half ("" if not known)
function VirtualReader:CoopP2Character()
  return self.coopP2Picked or self.coopP2Start or ""
end

function VirtualReader:GetStartIDP2()
  return self.coopP2Picked or self.coopP2Start or defaultAvatarName
end

-- P2's list moved onto a character: show it?
function VirtualReader:SelectItemP2(option)
  -- IsIGPValid gives the figure id or nothing, not true/false
  if self.listMode == "character" and self:IsIGPValid(option) then
    return true
  end
  return false
end

-- P2 picked a character: as the game's PickCharacter on PC, without the store (locked ones can't be picked)
-- and not P1's pick. True if taken.
function VirtualReader:PickCharacterP2(option)
  if self.listMode ~= "character" or option == nil or option == self.pickedChar then
    return false
  end
  if self:GetAvailableAvatarData(option) ~= nil and not self:CharacterLocked(option) and self:IsIGPValid(option) then
    self.coopP2Picked = option
    return true
  end
  return false
end

return VirtualReader
