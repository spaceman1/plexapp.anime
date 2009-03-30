from PMS import Plugin, Log, DB, Thread, XML, HTTP, JSON, RSS, Utils, Prefs
from PMS.MediaXML import MediaContainer, DirectoryItem, WebVideoItem, MediaItem
import re, gzip, pickle, string, unicodedata

PLUGIN_PREFIX   = "/video/anime"
TV_INDEX        = "http://www.zomganime.com/anime-series-list/"
MOVIE_INDEX     = "http://www.zomganime.com/anime/movies/"
META_BASE       = "http://anidb.net/perl-bin/animedb.pl?show=animelist&adb.search="
META_FOOTER     = "&do.search=search"
META_START      = "http://anidb.net/perl-bin/"

# art-default from http://www.flickr.com/photos/brandnewbrain/132295211/
# licensed as CC Attribution-Noncommercial-Share Alike 2.0 Generic

# icon-default based on http://www.flickr.com/photos/evilnolo/12430860/
# licensed as CC Attribution-Noncommercial-Share Alike 2.0 Generic
# and plex logo

####################################################################################################
def Start():
  Plugin.AddRequestHandler(PLUGIN_PREFIX, HandleVideosRequest, "Anime", "icon-default.png", "art-default.jpg")
  Plugin.AddViewGroup("Details", viewMode="InfoList", contentType="items")
  Plugin.AddViewGroup("PlainList", viewMode="List", contentType="items")
  Plugin.AddViewGroup("EpisodeList", viewMode="Episodes", contentType="items")
####################################################################################################

# TODO: Grab first 'TV Series' (not OVA)
# TODO: FIX site configuration

def HandleVideosRequest(pathNouns, count):

  devMode = True

  if len(Plugin.Dict) == 0 :    
    Plugin.Dict['tv'] = dict()
    Plugin.Dict['movie'] = dict()

  if count == 0 :
    dir = MediaContainer(art="art-default.jpg", viewGroup='PlainList' , title1="Anime")
    dir.AppendItem(DirectoryItem('tv', 'TV Series', '', ''))
    dir.AppendItem(DirectoryItem('movie', 'Movies', '', ''))

  elif count == 1 :
    # Show/Movie Names menu
    if pathNouns[0] == 'tv' : secondTitle = 'TV Series'
    else : secondTitle = 'Movies'
    dir = MediaContainer(art="art-default.jpg", viewGroup='Details', title1="Anime", title2= secondTitle)
    Log.Add(pathNouns)
    dirItems = list()

    if pathNouns[0] == 'tv' : 
      indexPath = TV_INDEX
      theXPath = '//div[@class="ddmcc"]/ul/ul/li/a'
    elif pathNouns[0] == 'movie' : 
      indexPath = MOVIE_INDEX
      theXPath = '//ul[@class="catg-post-list"]/li/a'

    for item in XML.ElementFromURL(indexPath, True).xpath(theXPath):
      showName = string.strip(item.text)
      showPath = Utils.EncodeStringToUrlPath(item.get('href'))
      show = GetMetadatum(pathNouns[0], showName)
      encodedShowName = showName.encode('utf-8','xmlcharrefreplace')

      # encodedShowName = ' ' + showName + ' '
      # encodedShowName = encodedShowName.encode('idna')
      # Log.Add(encodedShowName)

      # if pathNouns[0] == 'tv' :
      dirItem = DirectoryItem(Utils.EncodeStringToUrlPath(showPath + '$' + encodedShowName), showName, show['image'], show['description'])
     

      dirItems.append(dirItem)
      dir.AppendItem(dirItem)

    if devMode : Thread.Run(GetMetadata, (pathNouns[0], dirItems[0:15]))
    else : Thread.Run(GetMetadata, (pathNouns[0], dirItems))

  elif count == 2 :
    # Episodes menu
    if pathNouns[0] == 'tv' : theTitle = 'Anime TV Series'
    else : theTitle = 'Anime Movies'
    urlAndName = Utils.DecodeUrlPathToString(pathNouns[1])
    urlAndName = re.split(r'\$', urlAndName)
    Log.Add(urlAndName)
    path = Utils.DecodeUrlPathToString(urlAndName[0])
    showName = string.strip(urlAndName[1])
    dir = MediaContainer(art="art-default.jpg", viewGroup='EpisodeList', title1=theTitle, title2=showName)
    Log.Add(path)

    if pathNouns[0] == 'movie' :
      show  = Plugin.Dict['movie'][showName]
      Log.Add(getFlashUrl(path))
      dirItem = WebVideoItem(getFlashUrl(path), showName, show['description'], '', show['image'])
      dir.AppendItem(dirItem)
    elif pathNouns[0] == 'tv' :
      vids = XML.ElementFromURL(path, True).xpath('//ol[@class="list"]//li/a') #'//ul[@class="catg-post-list"]//li/a')
      vids.reverse()
      for vid in vids:
        Log.Add(vid.text)
        if vid.text != None : 
          title = re.sub(r'.*(Episode.*)', r'\1', vid.text)

          try : 
            episodeNumber = re.search('\d+\.?\d*',title).group(0)
            theEpisode = Plugin.Dict[pathNouns[0]][showName]['episodes'][episodeNumber.lstrip('0')]
            longTitle = theEpisode['name']
            duration = theEpisode['duration']
          except :
            longTitle = title
            duration = ''

          pageUrl = vid.get('href')
          flashUrl = getFlashUrl(pageUrl)

          dir.AppendItem(WebVideoItem(flashUrl, longTitle, '', str(duration), ''))
        # Log.Add((flashUrl, longTitle, '', str(duration), ''))

  return dir.ToXML()

def getFlashUrl(pageUrl) :
  flash = XML.ElementFromURL(pageUrl, True).xpath('//div[@class="entry1"]/p/embed')
  try : flashUrl = flash[0].get('src')
  except : flashUrl = ''
  return flashUrl

def GetMetadatum(kind,theShowName) :
  try:
    theShow = Plugin.Dict[kind][theShowName]
    return theShow
  except:
    return dict({'description':'', 'image':'', 'episodes':()})
  
def getSearchPage(thePage) :
  searchPageZipped = Plugin.DataFilePath("searchPage.zip")
  HTTP.Download(thePage, searchPageZipped)
  try:
    f = gzip.open(searchPageZipped, 'rb')
    searchPage = f.read()
  except :
    f.close()
    f = open(searchPageZipped,'rb')
    searchPage = f.read()
  f.close()
  return searchPage  
  
def GetMetadata((kind, dirItems)):
  Log.Add('GetMetadata called')
  dictUpdated = False
  for item in dirItems:
    theShowName = item.GetAttr('name')
    theShowName = theShowName.encode('utf-8','xmlcharrefreplace') # Workaround for lack of Unicode support in some modules
    show = GetMetadatum(kind,theShowName)
    if (show['description'] == '' or show['image'] == '' or show['episodes'] == ()) and theShowName != 'Anime Movies' and theShowName != 'Uncategorized' :
      # Search engine won't match with :+~, remove them
      metaPage = META_BASE + HTTP.Quote(re.sub(r"(?u)[:+~]", " ", theShowName),True) + META_FOOTER

      searchPage = getSearchPage(metaPage)
      animes = XML.ElementFromString(searchPage, True).xpath('//table[@class="animelist"]/tr/td/a')
      if len(animes) != 0 :
        searchPage = getSearchPage(META_START + animes[0].get('href'))

      images = XML.ElementFromString(searchPage, True).xpath('//div[@class="image"]/img')
      descriptions = XML.ElementFromString(searchPage, True).xpath('//div[@class="desc"]')
      episodeNames = XML.ElementFromString(searchPage, True).xpath('//table[@id="eplist"]/tr/td/label')
      episodeNumbers = XML.ElementFromString(searchPage, True).xpath('//table[@id="eplist"]/tr/td/a')
      episodeDurations = XML.ElementFromString(searchPage, True).xpath('//table[@id="eplist"]/tr/td[@class="duration"]')

      if len(images) != 0 : show['image'] = images[0].get('src')
      else : show['image'] = ''

      if len(descriptions) != 0 : show['description'] = descriptions[0].text.strip()
      else : show['description'] = ''

      episodeDict = dict()
      for episodeNum in range(len(episodeNames)):
        theDuration = re.sub(r'(\d+).*', r'\1', episodeDurations[episodeNum].text)
        theDuration = 60000 * int(theDuration)
        # Log.Add(theDuration)
        episodeDict[episodeNumbers[episodeNum].text.lstrip('0')] = dict(name=episodeNames[episodeNum].text.strip(), duration=theDuration)

      show['episodes'] = episodeDict
      Plugin.Dict[kind][theShowName] = show
      if show['description'] == '' or show['image'] == '' or show['episodes'] == () : Log.Add('Get info for ' + theShowName + ' failed', False)
      else : 
        Log.Add('Get info for ' + theShowName + ' succeeded', False)
        dictUpdated = True

  if dictUpdated :
    Log.Add("Pickle power engage")
    savedDict = Plugin.Dict.copy()
    pickle_file = Plugin.DataFilePath("DictPickle")
    f = open(pickle_file, "w")
    pickle.dump(savedDict, f, 2)
    f.close()
    Log.Add("Metadata saved", False)


