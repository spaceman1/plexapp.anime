from PMS import *
from PMS.Objects import *
from PMS.Shortcuts import *


import re, gzip, pickle, string, unicodedata, datetime, time

PLUGIN_PREFIX = "/video/anime"
TV_INDEX = "http://www.zomganime.com/anime-series-list/"
MOVIE_INDEX = "http://www.zomganime.com/anime/movies/"
META_BASE = "http://anidb.net/perl-bin/animedb.pl?show=animelist&adb.search="
META_FOOTER = "&do.search=search"
META_START = "http://anidb.net/perl-bin/"
CACHE_TIME = 86400 # 1 day

# art-default http://www.flickr.com/photos/brandnewbrain/132295211/
# licensed as CC Attribution-Noncommercial-Share Alike 2.0 Generic

# icon-default based on http://www.flickr.com/photos/evilnolo/12430860/
# licensed as CC Attribution-Noncommercial-Share Alike 2.0 Generic
# and plex logo

# icon-tag http://www.flickr.com/photos/kupkup/363252190/
# licensed as CC Attribution-Noncommercial-Share Alike 2.0 Generic

# art-tag http://www.flickr.com/photos/flynnkc/3343106010/
# licensed as CC Attribution-Noncommercial-Share Alike 2.0 Generic

# icon-category http://www.flickr.com/photos/kasaa/2720618062/
# licensed as CC Attribution-Noncommercial 2.0 Generic

# art-category http://www.flickr.com/photos/kasaa/2557528143/
# licensed as CC Attribution-Noncommercial 2.0 Generic

# tv-icon http://www.flickr.com/photos/nickatkins/393947161/
# licensed as CC Attribution-Noncommercial-No Derivative Works 2.0 Generic

# movie-icon http://www.flickr.com/photos/jessflickr/127769116/
# licensed as CC Attribution-Noncommercial-No Derivative Works 2.0 Generic

####################################################################################################

def Start():
  Plugin.AddPrefixHandler(PLUGIN_PREFIX, MainMenu, L("Anime"))
  
  Plugin.AddViewGroup("Details", viewMode="InfoList", mediaType="items")
  Plugin.AddViewGroup("PlainList", viewMode="List", mediaType="items")
  Plugin.AddViewGroup("EpisodeList", viewMode="Episodes", mediaType="items")
  
  MediaContainer.title1 = L("Anime")
  MediaContainer.viewGroup = "EpisodeList"
  MediaContainer.art = R("art-default.jpg")
  
  HTTP.SetCacheTime(CACHE_TIME)
  
####################################################################################################

# DONE: Implement episode menu
# DONE: Add durations to movies
# DONE: Add Categories
# DONE: Write UpdateCache

# TODO: Allow users to set anidb id for a show
# TODO: FIX site configuration

def CreateDict():
  Dict.Set('tv', dict())
  Dict.Set('movie', dict())
  Dict.Set('tags', dict())
  Dict.Set('categories', dict())

####################################################################################################

def UpdateCache():
  # Get TV Page
  tvDir = TVMenu(0)
  GetMetadata(('tv', tvDir))
  # Get Movie Page
  movieDir = movieMenu(0)
  GetMetadata(('movie', movieDir))

####################################################################################################

def MainMenu():
  dir = MediaContainer()
  dir.Append(Function(DirectoryItem(TVMenu, title=L('TV Series'), thumb=R("icon-tv.jpg"))))
  dir.Append(Function(DirectoryItem(movieMenu, title=L('Movies'))))
  dir.Append(Function(DirectoryItem(tagMenu, title=L('Tags'), thumb=R("icon-tag.jpg"))))
  dir.Append(Function(DirectoryItem(categoryMenu, title=L('Categories'), thumb=R("icon-category.jpg"))))
  return dir

def TVMenu(sender):
  dir = MediaContainer()
  dir.title2 = L('TV Shows')
  dir.viewGroup = "Details"
  for item in GetXML(TV_INDEX, True).xpath('//div[@class="ddmcc"]/ul/ul/li/a'):
    showName = string.strip(item.text).encode('ascii','ignore')
    show = GetMetadatum('tv', showName)
    dir.Append(Function(DirectoryItem(episodeMenu, showName, thumb=show['image'], summary=show['description'])))
  #Thread.Create(GetMetadata, ('tv', dir))
  return dir
          
def movieMenu(sender):
  dir = MediaContainer()
  dir.title2 = L('Movies')
  dir.viewGroup = "Details"
  for item in GetXML(MOVIE_INDEX, True).xpath('//div[@class="content"]/ol/li/a[2]'):
    showName = string.strip(item.text)
    show = GetMetadatum('movie', showName)
    if len(show['episodes']) == 1:
      duration = show['episodes'].items()[0][1]['duration']
    else: duration = ''
    dir.Append(WebVideoItem(item.get('href'), L(showName), thumb=show['image'], summary=show['description'], duration=duration))
  #Thread.Create(GetMetadata, ('movie', dir))
  return dir
  
####################################################################################################
  
def tagMenu(sender):
  return smartMenu(L('Tags'), 'tags', showsByTag, "art-tag.jpg")
    
def categoryMenu(sender):
  return smartMenu(L('Categories'), 'categories', showsByCategory, "art-category.jpg")

def smartMenu(title, key, function, art):
  dir = MediaContainer()
  dir.title2 = title
  dir.viewGroup = "Details"
  dir.art = R(art)
  group = Plugin.Dict.Get(key).keys()
  group.sort()
  for anItem in group:
    dir.Append(Function(DirectoryItem(function, title=anItem, summary=Dict.Get(key)[anItem]['description'])))
  return dir

####################################################################################################

def showsByTag(sender):
  return smartSubMenu(L('Anime Tags'), 'tags', sender)

def showsByCategory(sender):
  return smartSubMenu(L('Anime Categories'), 'categories', sender)

def smartSubMenu(title, key, sender):
  dir = MediaContainer()
  groupName = sender.itemTitle
  dir.title1 = title
  dir.title2 = groupName
  dir.viewGroup = "Details"
  shows = (Plugin.Dict.Get(key)[groupName]['shows'])
  showKeys = shows.keys()
  showKeys.sort()
  for showName in showKeys:
    showData = GetMetadatum(shows[showName], showName)
    # TODO: add support for jumping to movie from here
    dir.Append(Function(DirectoryItem(episodeMenu, title=L(showName), summary=showData['description'], thumb=showData['image'])))
  return dir

####################################################################################################

def episodeMenu(sender):
  dir = MediaContainer()
  showName = sender.itemTitle
  dir.title1 = 'Anime TV Series'
  dir.title2 = showName
  dir.viewGroup = "EpisodeList"

  thePageSrc = HTTP.Request(url=TV_INDEX, cacheTime=CACHE_TIME)
  xmlElems = XML.ElementFromString(thePageSrc, True)
  showURL = findLinkNamed(showName, xmlElems.xpath('//div[@class="ddmcc"]/ul/ul/li/a'))
  
  vids = XML.ElementFromURL(showURL, True).xpath('//ol[@class="list"]//li/a[text()!=""]')
  vids.reverse()
  
  for vid in vids:
    title = re.sub(r'.*(Episode.*)', r'\1', vid.text)
    try : 
      episodeNumber = re.search('\d+\.?\d*',title).group(0)
      theEpisode = Plugin.Dict.Get('tv')[showName]['episodes'][episodeNumber.lstrip('0')]
      longTitle = theEpisode['name']
      duration = theEpisode['duration']
    except :
      longTitle = title
      duration = ''
    pageUrl = vid.get('href')
    dir.Append(WebVideoItem(pageUrl, title=longTitle, duration=str(duration)))

  return dir

def findLinkNamed(linkText, links):
  for aLink in links:
    if aLink.text == linkText:
      return aLink.get('href')
  return None

####################################################################################################

def GetMetadatum(kind, theShowName) :
  try:
    theShow = Plugin.Dict.Get(kind)[theShowName]
    return theShow
  except:
    return dict({'description':'', 'image':'', 'episodes':dict()})

####################################################################################################  

def GetMetadata((kind, dirItems)):
  Log('GetMetadata called')
  dictUpdated = False
  for item in dirItems:
    if 'title' in item.__dict__: theShowName = item.__dict__['title']
    else: theShowName = item.__dict__['name']
    theShowName = theShowName.encode('ascii','ignore')
    show = GetMetadatum(kind,theShowName)
    if (show['description'] == '' or show['image'] == '' or (show['episodes'] == () and kind == 'tv')) and theShowName != 'Anime Movies' and theShowName != 'Uncategorized' :
      showNeedsUpdate = False
      # Search engine won't match with :+~, remove them
      metaPage = META_BASE + String.Quote(re.sub(r"(?u)[:+~]", " ", theShowName),True) + META_FOOTER

      time.sleep(2) # Avoid AniDB flood ban
      searchPage = GetXML(metaPage, True)
      animes = searchPage.xpath('//table[@class="animelist"]/tr/td/a')
      # If we get back multiple results pick the first one
      if len(animes) != 0 :
        searchPage = GetXML(META_START + animes[0].get('href'), True)
        
      images = searchPage.xpath('//div[@class="image"]/img')
      descriptions = searchPage.xpath('//div[@class="desc"]')
      tags = searchPage.xpath('//div[@class="g_section tags"]/div/span')
      categories = searchPage.xpath('//div[@class="tagcloud"]/span')
      
      episodeNames = searchPage.xpath('//table[@id="eplist"]/tr/td/label')
      episodeNumbers = searchPage.xpath('//table[@id="eplist"]/tr/td/a')
      episodeDurations = searchPage.xpath('//table[@id="eplist"]/tr/td[@class="duration"]')        

      if len(images) != 0:
        show['image'] = images[0].get('src')
        showNeedsUpdate = True
      else : show['image'] = ''

      if len(descriptions) != 0:
        show['description'] = descriptions[0].text.strip().encode('ascii','ignore')
        showNeedsUpdate = True
      else : show['description'] = ''
      
      # Grab for Tags menu
      tagsNeedUpdate = False
      for aTag in tags:
        tagName = aTag.xpath('a')[0].text.title()
        tagDescription = aTag.xpath('a/span/span[2]')[0].text
        tagsDict = Dict.Get('tags')
        if not tagName in tagsDict:
          tagsDict[tagName] = dict(description=tagDescription, shows=dict())
          tagsNeedUpdate = True
        if not theShowName in tagsDict[tagName]['shows']:
          tagsDict[tagName]['shows'][theShowName] = kind
          tagsNeedUpdate = True

      if tagsNeedUpdate == True:
        Dict.Set('tags', tagsDict)

      # Grab for Categories menu
      categoriesNeedUpdate = False
      for aCategory in categories:
        categoryName = aCategory.xpath('a')[0].text.title()
        categoryDescription = aCategory.xpath('a/span/span[2]')[0].text
        categoryDict = Dict.Get('categories')
        if not categoryName in categoryDict:
          categoryDict[categoryName] = dict(description=categoryDescription, shows=dict())
          categoriesNeedUpdate = True
        if not theShowName in categoryDict[categoryName]['shows']:
          categoryDict[categoryName]['shows'][theShowName] = kind
          categoriesNeedUpdate = True

      if categoriesNeedUpdate == True:
        Dict.Set('categories', categoryDict)


          
      if kind == 'tv': 
        episodeRange = range(len(episodeNames))
      elif len(episodeDurations) != 0:
        episodeRange = (0,) # For movies only grab the duration of the entire movie (no chapters)
      else:
        episodeRange = list() # Handle no duration specified
 
      for episodeNum in episodeRange:
#        if not str(episodeNum) in show['episodes']:
        theDuration = re.sub(r'(\d+).*', r'\1', episodeDurations[episodeNum].text)
        theDuration = 60000 * int(theDuration)
        show['episodes'][episodeNumbers[episodeNum].text.lstrip('0')] = dict(name=episodeNames[episodeNum].text.strip(), duration=theDuration)
        showNeedsUpdate = True
        
      if showNeedsUpdate:
        dk = Dict.Get(kind)
        dk[theShowName] = show
        Dict.Set(kind, dk)
        Log('Get info for ' + theShowName + ' succeeded')
      else:
        Log('Get info for ' + theShowName + ' failed')

####################################################################################################
def GetXML(theUrl, use_html_parser=False):
  return XML.ElementFromString(HTTP.Request(url=theUrl,cacheTime=CACHE_TIME), use_html_parser)


####################################################################################################
