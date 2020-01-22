#!/usr/bin/python3
from aiohttp import web,ClientSession
from asyncio import run,sleep,create_task
from pathlib import Path
from subprocess import Popen
from sys import stderr
from threading import Thread
from re import compile
from urllib.parse import urlencode

APPID=390364
PERMS="manage_library"
AUTH_URL="https://connect.deezer.com/oauth/auth.php"
AC_URL="https://connect.deezer.com/oauth/access_token.php"
API_URL="https://api.deezer.com"

TRACK="/user/me/tracks"
U_PLAYLISTS="/user/me/playlists"
PLAYLIST="/playlist/"

REDIRECT_URL="http://127.0.0.1:8080"
BROWSERS=("xdg-open",'firefox','chromium','google-chrome')
TOKEN_RE = compile("access_token=(\w{51})&expires=(\d+)")
APP_SECRET="REDACTED_APP_SECRET"
NAME_TABLE = str.maketrans(" /()","_-..",".?'")
verbose=True
def get_req_url():
	payload = { "app_id": APPID, "perms": PERMS, "redirect_uri": REDIRECT_URL }
	return '?'.join((AUTH_URL, urlencode(payload)))

def try_run(prog,url):
	try:
		Popen([prog, url])
	except FileNotFoundError:
		return False
	return True

def launch_browser(url):
	for prog in BROWSERS:
		if try_run(prog,url):
			return True
	print("Error: Failed to find browser", file=stderr)
	return False	

def str_to_name(s):
	return s.translate(NAME_TABLE).encode(encoding="ascii",errors="ignore")
async def fetch_loved_songs(cs,token):
	url = API_URL + TRACK
	payload = { "access_token": token, "output": "json" } 
	sl = {}
	async with cs.get(url, params=payload) as res:
		res.raise_for_status()
		json = await res.json()
		if len(json['data']) < 25:
			for song in json['data']:
				name = b'.'.join((str_to_name(song['artist']['name']),
					str_to_name(song['album']['title']),b'jpg'))
				picture = song['album'].get('cover_xl')
				if picture is None:
					print("Warning no xl cover found for %s, skipping...", name)
					continue
				sl[name] = picture
			return sl	

	url = API_URL + U_PLAYLISTS
	async with cs.get(url, params=payload) as res:
		res.raise_for_status()
		json = await res.json()
		for pl in json['data']:
			if pl['is_loved_track']:
				ID = pl['id']
				break
	url = ''.join((API_URL, PLAYLIST, str(ID)))
	async with cs.get(url, params=payload) as res:
		res.raise_for_status()
		json = await res.json()
		for song in json['tracks']['data']:
			name = b'.'.join((str_to_name(song['artist']['name']),
				str_to_name(song['album']['title']),b'jpg'))
			picture = song['album'].get('cover_xl')
			if picture is None:
				print("Warning no xl cover found for %s, skipping...", name)
				continue
			sl.setdefault(name, picture)

	return sl

async def fetch_cover(path,url,cs):
	try:
		if verbose:
			print("Downloading cover for %s ...", path)
		async with cs.get(url,raise_for_status=True) as res:
			with open(path,"wb") as f:
				f.write(await res.read())
				print("Successfully wrote %s")
	except e:
		print("Error: Failed to get file for %s, skipping" % e)

async def test():
	print("agwsg")	

async def fetch_covers_async(code):
	if verbose:
		print("Getting Deezer access code...",file=stderr)
	payload = { "app_id": APPID, "secret": APP_SECRET, "code": code }
	async with ClientSession() as cs:
		res = await cs.get(AC_URL, params=payload)
		res.raise_for_status()
		text = await res.text()
		print(text)
		match = TOKEN_RE.fullmatch(text) 
		if match is None:
			print("Error: unexpected access token format from Deezer. Quiting", file=stderr)
			return
		token = match.group(1)
		songs = await fetch_loved_songs(cs,token)
		futures = []	
		tasks = [create_task(fetch_cover(song,songs[song],cs)) for song in songs 
			if not Path(song.decode()).exists() and not await sleep(.1)]
		
		[await future for future in tasks]
				
				
def fetch_covers(code):
	print("test")
	run(fetch_covers_async(code))
	
		

def reqhandler(request):
	code = request.query.get("code")
	if not code:
		return web.Response(text="Bad code recieved!!", status=400)
	
	Thread(target=fetch_covers,args=(code,),daemon=True).start()
	return web.Response(text="Starting pull of albums")

	
	
def get_token_from_browser():
	app = web.Application()
	app.router.add_get('/', reqhandler)
	web.run_app(app)

def main():
	launch_browser(get_req_url())
	get_token_from_browser()

if __name__=="__main__":
	main()
