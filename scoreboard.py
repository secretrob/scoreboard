#!/usr/bin/env python
from PIL import Image, ImageDraw, ImageFont, ImageSequence
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from datetime import datetime, timezone, timedelta
import configparser
import logging
import requests
import json
import time
import math
import random

class cacheInfo:
    def __init__(self):
        self.lastCacheTime=''
        self.gameCacheDelay=0

def get_frames(path,size):
    """Returns an iterable of gif frames."""
    frames = []
    with Image.open(path) as gif:
        for frame in ImageSequence.Iterator(gif):
            frame = frame.convert('RGB').resize(size)
            frames.append(frame)
        return frames


def display_gif(path,number_of_loops,location,size=(32,32),speed=50):
    loops_done=0    
    while True:
        for frame in get_frames(path,size):
            matrix.SetImage(frame, location[0])
            if speed=='gif':
                duration=frame.info['duration']
            else:
                duration=speed
            time.sleep(duration/1000)
        loops_done+=1
        if loops_done>=number_of_loops:
            return

def getTeamData():
    """Get team names and abreviations from the NHL API, return information as a list of dictionaries.

    Returns:
        teams (list of dictionaries): Each dict contains the longform name and abbreviation of a single NHL team.
    """
    
    # Call the NHL Teams API. Store as a JSON object.
    # check for cache file and use that first
    with open(sbPath + "cache/teams.json", 'r+', encoding='utf-8') as teamsJsonFile:
        if teamsJsonFile.read(1):            
            teamsJsonFile.seek(0)
            teamsJson = json.load(teamsJsonFile)
        else:            
            teamsResponse = requests.get(url="https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/teams")
            teamsJson = teamsResponse.json()
            json.dump(teamsJson, teamsJsonFile, ensure_ascii=False, indent=4)
    teamsJsonFile.close()
    # Decalare an empty list to hold the team dicts.
    teams = []

    # For each team, build a dict recording it's name and abbreviation. Append this to the end of the teams list.
    for team in teamsJson['sports'][0]['leagues'][0]['teams']:               
        teamDict = {
                'Team Name': team['team']['displayName'],
                'Team Abbreviation': team['team']['abbreviation']
        }
        # Append dict to the end of the teams list.
        teams.append(teamDict)
    return teams

def getGameData(teams,cacheData):
    """Get game data for all of todays games from the NHL API, returns games as a list of dictionaries.
    Args:
        teams (list of dictionaries): Team names and abberivations. Needed as the game API doen't return team abbreviations.
    Returns:
        games (list of dictionaries): All game info needed to display on scoreboard. Teams, scores, start times, game clock, etc.
    """
    # Call the NHL API for today's game info. Save the rsult as a JSON object.
    gamesstart=cacheData.lastCacheTime
    gamesend=cacheData.lastCacheTime + timedelta(seconds=cacheData.gameCacheDelay)
    openType='r+'    
    if gamesend<=gamesstart:
        cacheData.lastCacheTime=datetime.now()
        cacheData.gameCacheDelay=0
        openType='w+' #flush and pull api
    with open(sbPath + "cache/games.json", openType, encoding='utf-8') as gamesJsonFile:
        if gamesJsonFile.read(1):            
            gamesJsonFile.seek(0)
            eventsJson = json.load(gamesJsonFile)
        else:            
            eventsResponse = requests.get(url="https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard")
            eventsJson = eventsResponse.json()
            json.dump(eventsJson, gamesJsonFile, ensure_ascii=False, indent=4)
    gamesJsonFile.close()    
    # Decalare an empty list to hold the games dicts.
    games = []

    # For each game, build a dict recording it's information. Append this to the end of the teams list.
    if eventsJson['events']: # If games today.
        allGamesEnded = True
        earliestGame = utcToLocal(datetime(2037,1,1,0,0,0,0,timezone.utc))
        for event in eventsJson['events']:
            # Prep the period data for consistancy. This data doesn't exist in the API responce until game begins.
            if event['status']['period']>0:
                perInfo = event['status']['type']['shortDetail'].split(' - ')
                if len(perInfo)>1:
                    perName = perInfo[1]
                    perTimeRem = perInfo[0]
                else:
                    perName = perInfo[0]
                    perTimeRem = "0:00"
            else:
                perName = "Not Started"
                perTimeRem = "Not Started"

            # Prep the dict data.
            gameDict = {
                'Game ID': event['id'],
                #trash hack using 0/1 for now
                'Home Team': event['competitions'][0]['competitors'][0]['team']['displayName'],                
                'Home Abbreviation': event['competitions'][0]['competitors'][0]['team']['abbreviation'],
                'Away Team': event['competitions'][0]['competitors'][1]['team']['displayName'],                 
                'Away Abbreviation': event['competitions'][0]['competitors'][1]['team']['abbreviation'],
                'Home Score': event['competitions'][0]['competitors'][0]['score'],
                'Away Score': event['competitions'][0]['competitors'][1]['score'],                
                'Start Time UTC':  datetime.strptime(event['competitions'][0]['date'], '%Y-%m-%dT%H:%MZ'), # Extracts the startime from what's given by the API.
                'Start Time Local': utcToLocal(datetime.strptime(event['competitions'][0]['date'], '%Y-%m-%dT%H:%MZ')), # Converts the UTC start time to the RPi's local timezone.
                'Status': event['status']['type']['name'],
                'Detailed Status': event['status']['type']['description'],
                'Period Number': event['status']['period'],
                'Recap': '',
                'Period Name': perName,
                'Period Time Remaining': perTimeRem
            }

            if event['competitions'][0].get('headlines'):
                gameDict['Recap']=event['competitions'][0]['headlines'][0]['shortLinkText']

            # Check to see if we reset the cache
            if gameDict['Status']=="STATUS_SCHEDULED":
                allGamesEnded = False
                earliestGame = gameDict['Start Time Local'] if gameDict['Start Time Local'] < earliestGame else earliestGame
            elif gameDict['Status']!="STATUS_FINAL":
                allGamesEnded = False
                earliestGame = utcToLocal(datetime(2037,1,1,0,0,0,0,timezone.utc))

            # Append the dict to the games list.
            games.append(gameDict)

            # Sort list by Game ID. Ensures order doesn't change as games end.
            games.sort(key=lambda x:x['Game ID'])
        
        if earliestGame!=datetime(2099,1,1,0,0,0,0,timezone.utc) and cacheData.gameCacheDelay<=0:
            cacheData.gameCacheDelay=timeUntil(earliestGame,True).seconds
        elif allGamesEnded and cacheData.gameCacheDelay<=0:
            cacheData.gameCacheDelay=timeUntil(datetime.now() + timedelta(hours = 1)).seconds
        else:
            cacheData.gameCacheDelay=5
    
    return games

def getMaxBrightness(time):
    """ Calculates the maximum brightness and fade step incremements based on the time of day.

    Args:
        time (int): Hour of the day. Can be 0-23.

    Returns:
        maxBrightness (int): The maximum brightness for the LED display.
        fadeStep (int): The increments that the display should fade up and down by.
    """
    
    # If the time is midnight, set the time to 1am to avoid the display fulling turning off.
    if time == 0:
        time = 1

    if disableFade:
        time=12

    # Max brightness is the time divided by 12 and multiplied by 100. For pm times, the difference between 24 and the time is used.
    # This means that max brightness is at noon, with the lowest from 11pm through 1am (because of the above edge case).
    maxBrightness = math.ceil(100 * time / 12 if time <= 12 else 100 * (24-time)/12)
    
    # If the previous calculation results in a birhgtness less than 15, set brightnes to 15.
    maxBrightness = maxBrightness if maxBrightness >= 15 else 15

    # Fade step divides the maxBrightness into 15 segments. Floor since you can't have fractional brightness.
    fadeStep = math.ceil(maxBrightness/15)

    return maxBrightness, fadeStep

def cropImage(image):
    """Crops all transparent space around an image. Returns that cropped image."""

    # Get the bounding box of the image. Aka, boundries of what's non-transparent.
    bbox = image.getbbox()

    # Crop the image to the contents of the bounding box.
    image = image.crop(bbox)

    # Determine the width and height of the cropped image.
    (width, height) = image.size
    
    # Create a new image object for the output image.
    croppedImage = Image.new("RGB", (width, height), (0,0,0,255))

    # Paste the cropped image onto the new image.
    croppedImage.paste(image)

    return croppedImage

def utcToLocal(utc_dt):
    """Returns a time object converted to the local timezone set on the RPi."""
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=None)

def isCurrentTimeBetween(startTime, endTime):
    now = datetime.now()    
    if startTime < endTime:
        return startTime <= now <= endTime
    else:
        return now >= startTime or now <= endTime

def timeUntil(startTime,utc=False):
    now = datetime.now()
    if utc: now = utcToLocal(datetime.now(timezone.utc))
    return startTime - now

def checkGoalScorer(game, gameOld):
    """Checks if a team has scored.

    Args:
        game (dict): All information for a specific game.
        gameOld (dict): Same information from one update cycle ago.

    Returns:
        scoringTeam (string): If either team has scored. both/home/away/none.
    """

    # Check if either team has score by compare the score of the last cycle. Set scoringTeam accordingly.
    if game['Away Score'] > gameOld['Away Score'] and game['Home Score'] == gameOld['Home Score']:
        scoringTeam = "away"
    elif game['Away Score'] == gameOld['Away Score'] and game['Home Score'] > gameOld['Home Score']:
        scoringTeam = "home"
    elif game['Away Score'] > gameOld['Away Score'] and game['Home Score'] > gameOld['Home Score']:
        scoringTeam = "both"
    else:
        scoringTeam = "none"

    return scoringTeam

def buildGame(game, gameOld, scoringTeam):
    """Args:
        game (dict): All information for a specific game.
        gameOld (dict): The same information, but from one cycle ago.
        scoringTeam (string): If the home team, away team, or both, or neither scored.
    """

    # Add the logos of the teams inivolved to the image.
    displayLogos(game['Away Abbreviation'],game['Home Abbreviation'])

    startTime = game['Start Time Local']
    startTime = startTime.time().strftime('%I:%M %p')
    startTime = str(startTime) # Cast to a string for easier parsing.
    if startTime[0]=="0": #strip leading 0
        startTime=startTime[1:]
    
    # Add the period to the image.
    displayPeriod(game['Period Number'], game['Period Name'], game['Period Time Remaining'], game['Status'], startTime)
    # Add the current score to the image. Note if either team scored.
    return displayScore(game['Status'],game['Away Score'], game['Home Score'], scoringTeam)

def buildNoGamesToday():
    """Adds all aspects of the no games today screen to the image object."""

    # Add the NHL logo to the image.
    nhlLogo = Image.open(sbPath + "assets/images/NHL_Logo_Simplified.png")
    nhlLogo = cropImage(nhlLogo)
    nhlLogo.thumbnail((40,30))
    image.paste(nhlLogo, (1, 1))

    # Add "No Games Today" to the image.
    draw.text((32,0), "No", font=fontDefault, fill=fillWhite)
    draw.text((32,10), "Games", font=fontDefault, fill=fillWhite)
    draw.text((32,20), "Today", font=fontDefault, fill=fillWhite)

def buildLoading():
    """Adds all aspects of the loading screen to the image object."""

    # Add the NHL logo to the image.
    nhlLogo = Image.open(sbPath + "assets/images/NHL_Logo_Simplified.png")
    nhlLogo = cropImage(nhlLogo)
    nhlLogo.thumbnail((40,30))
    image.paste(nhlLogo, (1, 1))

    # Add "Now Loading" to the image.
    draw.text((29,7), "Loading", font=fontDefault, fill=fillWhite)

def fadeImage(im, reverse=False, black=255, gradient_magnitude=1.):
    if im.mode != 'RGBA':
        im = im.convert('RGBA')
    width, height = im.size
    gradient = Image.new('L', (width, 1), color=0xFF)    
    for x in range(width):
        # gradient.putpixel((x, 0), 255-x)        
        if reverse:
            gradient.putpixel((x, 0), black-int(black * (1 - gradient_magnitude * float(x)/width)))
        else:
            gradient.putpixel((x, 0), int(black * (1 - gradient_magnitude * float(x)/width)))
    alpha = gradient.resize(im.size)
    black_im = Image.new('RGBA', (width, height), color=0) # i.e. black
    black_im.putalpha(alpha)    
    gradient_im = Image.alpha_composite(im, black_im)
    return gradient_im


def displayLogos(awayTeam, homeTeam):
    """Adds the logos of the home and away teams to the image object, making sure to not overlap text and center logos.

    Args:
        awayTeam (string): Abbreviation of the away team.
        homeTeam (string): Abbreviation of the home team.
    """

    # Difine the max width and height that a logo can be.
    logoSize = (40,30)

    # Load, crop, and resize the away team logo.
    awayLogo = Image.open(sbPath + "assets/images/team logos/png/" + awayTeam + ".png")
    awayLogo = cropImage(awayLogo)
    awayLogo.thumbnail(logoSize)

    # Load, crop, and resize the home team logo.
    homeLogo = Image.open(sbPath + "assets/images/team logos/png/" + homeTeam + ".png")
    homeLogo = cropImage(homeLogo)
    homeLogo.thumbnail(logoSize)

    # Record the width and heights of the logos.
    awayLogoWidth, awayLogoHeight = awayLogo.size
    homeLogoWidth, homeLogoHeight = homeLogo.size

    middleAdj = int(firstMiddleCol) 

    # Add the logos to the image.
    # Logos will be bounded by the text region, and be centered vertically.
    image.paste(fadeImage(awayLogo,True,225), (middleAdj-awayLogoWidth, math.floor((options.rows-awayLogoHeight)/2)))
    image.paste(fadeImage(homeLogo,False,225), (middleAdj+22, math.floor((options.rows-homeLogoHeight)/2)))
    
    if debug:
        draw.line([(63,0),(63,options.rows)],fill=fillRed,width=2)

def displayPeriod(periodNumber, periodName, timeRemaining, status, startTime):
    """Adds the current period to the image object.

    Args:
        periodNumber (int): [description]
        periodName (string): [description]
        timeRemaining (string): [description]
    """    
    if status=="STATUS_SCHEDULED":
        timeRemaining=startTime
        periodName="Today"
    if status!="STATUS_FINAL":
        draw.text((firstMiddleCol+12,13), timeRemaining, font=fontDefault, fill=fillWhite, anchor="ms")        

    draw.text((firstMiddleCol+12,7), periodName, font=fontDefault, fill=fillWhite, anchor="ms")

def displayScore(status, awayScore, homeScore, scoringTeam = "none"):
    """Add the score for both teams to the image object.
    Args:
        awayScore (int): Score of the away team.
        homeScore (int): Score of the home team.
        scoringTeam (str, optional): The team that scored if applicable. Options: "away", "home", "both", "none". Defaults to "none".
    """    
    goalData = {'score':'','location':'','secondScore':'','secondLocation':(0,0),'both':False}
    if status=="STATUS_SCHEDULED":
        draw.text((firstMiddleCol+5,17), "AT", font=fontLarge, fill=fillWhite)
        return goalData
    
    # Add the hypen to the image.
    draw.text((firstMiddleCol+9,17), "-", font=fontLarge, fill=fillWhite)
    # If no team scored, add both scores to the image.
    if scoringTeam == "none":
        draw.text((firstMiddleCol+2,18), str(awayScore), font=fontLarge, fill=fillWhite)
        draw.text((firstMiddleCol+15,18), str(homeScore), font=fontLarge, fill=(fillWhite))
    # If either or both of the teams scored, add that number to the image in red.
    elif scoringTeam == "away":
        draw.text((firstMiddleCol-1,18), str(awayScore), font=fontLarge, fill=fillRed)
        draw.text((firstMiddleCol+17,18), str(homeScore), font=fontLarge, fill=fillWhite)
        goalData['score']=str(awayScore)
        goalData['location']=(firstMiddleCol-1,18)
    elif scoringTeam == "home":
        draw.text((firstMiddleCol-1,18), str(awayScore), font=fontLarge, fill=fillWhite)
        draw.text((firstMiddleCol+17,18), str(homeScore), font=fontLarge, fill=fillRed)
        goalData['score']=str(homeScore)
        goalData['location']=(firstMiddleCol+17,18)
    elif scoringTeam == "both":
        draw.text((firstMiddleCol-1,18), str(awayScore), font=fontLarge, fill=fillRed)
        draw.text((firstMiddleCol+17,18), str(homeScore), font=fontLarge, fill=fillRed)
        goalData = {'score':str(awayScore), 'location':(firstMiddleCol-1,18), 'secondScore':str(homeScore), 'secondLocation':(firstMiddleCol+17,18), 'both':True}

    return goalData

def displayGoal(goalData):
    if goalData['score']=='':
        return
    # Show lamp and goal info
    display_gif(sbPath + "assets/images/hockey-goal.gif",1,(0,0),(fullWidth,options.rows))
    # If both teams have scored.
    if goalData['both'] == True:        
        # Fade both numbers to white.
        for n in range(50, 256):
            draw.text(goalData['location'], goalData['score'], font=fontLarge, fill=(255, n, n, 255))
            draw.text(goalData['secondLocation'], goalData['secondScore'], font=fontLarge, fill=(255, n, n, 255))
            matrix.SetImage(image)
            time.sleep(.0015)    
    # If one team has scored.
    else:
        # Fade number to white.
        for n in range(50, 256):
            draw.text(goalData['location'], goalData['score'], font=fontLarge, fill=(255, n, n, 255))
            matrix.SetImage(image)
            time.sleep(.0015)

def runClock(duration):
    #run for duration in seconds
    clockstart=datetime.now()
    clockend=clockstart + timedelta(seconds=duration)
    moveTimer=0
    x=firstMiddleCol+12
    y=centerHeight
    while True:
        moveTimer+=0.1
        if moveTimer>=10: #screensaver
            x=random.randrange(9,fullWidth-8,1) #width of ~20
            y=random.randrange(4,endHeight-2,1) #height of 5
            moveTimer=0
        current = time.strftime("%H:%M")
        draw.rectangle(((0,0),(endPixel,endHeight)), fill=fillBlack) #blank screen
        draw.text((x,y), current, font=fontDefault, fill=fillWhite, anchor="mm")
        matrix.SetImage(image)
        time.sleep(0.1)
        if isCurrentTimeBetween(clockstart,clockend)==False:
            return        

def runScoreboard():
    """Runs the scoreboard geting scores and other game data and cycles through them in an infinite loop."""

    # Initial calculation and setting of the max brightness.
    maxBrightness, fadeStep = getMaxBrightness(int(datetime.now().strftime("%H")))
    matrix.brightness = maxBrightness

    # Build the loading screen.
    buildLoading()
    matrix.SetImage(image) # Set the matrix to the image.

    networkError = False

    # Try to get team and game data. Max of 100 attempts before it gives up.
    for i in range(100):
        try:
            teams = getTeamData()
            games = getGameData(teams,cacheData)
            gamesOld = games # Needed for checking logic on initial loop.            
            cycleTime = round(60/len(games))
            networkError = False
            break

        # In the event that the NHL API cannot be reached, set the bottom right LED to red.
        # TODO: Make this more robust for specific fail cases.
        except Exception as e:
            logger.error('Error %s', '', exc_info=e)
            networkError = True
            if i >= 10:
                draw.rectangle(((endPixel,endHeight),(endPixel,endHeight)), fill=fillRed)
                matrix.SetImage(image)
            time.sleep(1)

    # Wait one extra second on the loading screen. Users thought it was too quick.
    time.sleep(1)

    # Fade out.
    for brightness in range(maxBrightness,0,-fadeStep):
        matrix.brightness = brightness
        matrix.SetImage(image)
        time.sleep(.025)

    # "Wipe" the image by writing over the entirity with a black rectangle.
    draw.rectangle(((0,0),(endPixel,endHeight)), fill=fillBlack)
    matrix.SetImage(image)

    while True:        
        # Update the maxBrightness and fadeSteps.
        maxBrightness, fadeStep = getMaxBrightness(int(datetime.now().strftime("%H")))

        # Adjusting cycle time to only hit API once a min
        cycleTime = round(60/len(games))
        if isCurrentTimeBetween(timeStart,timeEnd):
            # If there's games today.
            if games:
                # Loop through both the games and gamesOld arrays.
                for game, gameOld in zip(games, gamesOld):

                    # Check if either team has scored.
                    scoringTeam = checkGoalScorer(game, gameOld)

                    # If the game is postponed, build the postponed screen.
                    #if game['Detailed Status'] == "Postponed":
                    #    buildGamePostponed(game)

                    goalData = buildGame(game, gameOld, scoringTeam)                    

                    # Set bottom right LED to red if there's a network error.
                    if networkError:
                        draw.rectangle(((endPixel,endHeight),(endPixel,endHeight)), fill=fillRed)

                    # Fade up to the image.
                    for brightness in range(0,maxBrightness,fadeStep):
                        matrix.brightness = brightness
                        matrix.SetImage(image)
                        time.sleep(.025)

                    # Hold the screen before fading.
                    if confCycleTime>cycleTime:
                        cycleTime=confCycleTime

                    displayGoal(goalData)

                    time.sleep(cycleTime)

                    # Fade down to black.
                    for brightness in range(maxBrightness,0,-fadeStep):
                        matrix.brightness = brightness
                        matrix.SetImage(image)
                        time.sleep(.025)

                    # Make the screen totally blank between fades.
                    draw.rectangle(((0,0),(endPixel,endHeight)), fill=fillBlack) 
                    matrix.SetImage(image)

            # If there's no games, build the no games today sceen, then wait 10 minutes before checking again.
            else:
                buildNoGamesToday()
                matrix.brightness = maxBrightness
                matrix.SetImage(image)
                time.sleep(600)
                draw.rectangle(((0,0),(endPixel,endHeight)), fill=fillBlack)
            
            # Refresh the game data.
            # Record the data of the last cycle in gamesOld to check for goals.
            try:
                gamesOld = games

                games = getGameData(teams,cacheData)
                networkError = False
            except:
                logger.info("Network Error")
                networkError = True
        else:
            # "Wipe" the image by writing over the entirity with a black rectangle.
            draw.rectangle(((0,0),(endPixel,endHeight)), fill=fillBlack)
            matrix.brightness=maxBrightness
            matrix.SetImage(image)
            waitTime = timeUntil(timeStart)
            dispTime = str(waitTime + timedelta(days=-1*waitTime.days)).split(':')
            if waitTime.seconds>300:
                logger.info("Sleeping due to screen off times. Will wake and try API again in " + dispTime[0] + " hours and " + dispTime[1] + " mins.")
                draw.rectangle(((0,0),(endPixel,endHeight)), fill=fillBlack) #blank screen        
                draw.text((firstMiddleCol+12,centerHeight-5), "Sleep - Wake in", font=fontDefault, fill=fillWhite, anchor="mm")
                draw.text((firstMiddleCol+12,centerHeight+5), dispTime[0] + " hrs & " + dispTime[1] + " mins", font=fontDefault, fill=fillWhite, anchor="mm")
                matrix.SetImage(image)
                time.sleep(5)
            if waitTime.seconds>60:
                logger.info("Waking up in " + str(waitTime.seconds) + " seconds.")
                draw.rectangle(((0,0),(endPixel,endHeight)), fill=fillBlack) #blank screen
                draw.text((firstMiddleCol+12,centerHeight), "Start in " + str(waitTime.seconds), font=fontDefault, fill=fillWhite, anchor="mm")
                matrix.SetImage(image)                
                if showClockWhileSleeping:
                    runClock(waitTime.seconds-60)
                else:
                    time.sleep(waitTime.seconds-60) #sleep until one min prior to start time and check again

if __name__ == "__main__":
    # Read in configs from INI
    config = configparser.ConfigParser()
    #config.read('setup/scoreboard.conf')
    config.read('/etc/rgb_scoreboard.conf')
    
    # Configure options for the matrix
    options = RGBMatrixOptions()
    options.rows = config.getint('matrix', 'rows')
    options.cols = config.getint('matrix', 'cols')
    options.chain_length = config.getint('matrix', 'chain_length')
    options.parallel = config.getint('matrix', 'parallel')
    options.gpio_slowdown= config.getint('matrix', 'gpio_slowdown')
    options.hardware_mapping = config.get('matrix', 'hardware_mapping')
    options.drop_privileges = False

    # Define a matrix object from the options.
    matrix = RGBMatrix(options = options)

    # Define an image object that will be printed to the matrix.
    image = Image.new("RGB", (options.cols*options.chain_length, options.rows))

    # Define a draw object. This will be used to draw shapes and text to the image.
    draw = ImageDraw.Draw(image)

    sbPath = config.get('scoreboard', 'path')

    fontMedium = ImageFont.truetype(sbPath + "assets/fonts/04B_24__.TTF",8)
    fontLarge = ImageFont.truetype(sbPath + "assets/fonts/score_large.otf",16)
    fontDefault = fontMedium

    # Declare text colours that are needed.
    fillWhite = 255,255,255,255
    fillBlack = 0,0,0,255
    fillRed = 255,50,50,255

    # Define the first col that can be used for center text.
    # i.e. the first col you can use without worry of logo overlap.
    fullWidth = options.cols*options.chain_length
    centerWidth = fullWidth/2
    centerHeight = options.rows-round(options.rows/2)    
    firstMiddleCol = centerWidth-11
    endPixel = fullWidth-1
    endHeight = options.rows-1

    # Define the number of seconds to sit on each game.
    confCycleTime = config.getint('scoreboard', 'confCycleTime')

    now=datetime.now()
    timeStart=datetime.strptime(config.get('scoreboard', 'timeStart'), "%H:%M%p").replace(month=now.month,day=now.day,year=now.year)
    timeEnd=datetime.strptime(config.get('scoreboard', 'timeEnd'), "%H:%M%p").replace(month=now.month,day=now.day,year=now.year)
    if timeEnd<now: timeEnd=timeEnd+timedelta(days=1)
    disableFade=config.getboolean('scoreboard', 'disableFade')
    debug=config.getboolean('scoreboard', 'debug')
    showClockWhileSleeping=config.getboolean('scoreboard', 'showClockWhileSleeping')

    cacheData = cacheInfo()
    cacheData.lastCacheTime=datetime.now()
    cacheData.gameCacheDelay=0

    

    logging.basicConfig(filename=config.get('scoreboard','log'),
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.ERROR)

    logging.info("Running Scoreboard")
    logger = logging.getLogger('scoreboard')    

    # Run the scoreboard.
    runScoreboard()

    #penalty animation - need to check for pen: #display_gif("assets/images/penalty_animation.gif",2,True)
