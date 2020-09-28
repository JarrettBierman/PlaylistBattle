from flask import Flask, render_template, request, redirect, session, url_for
import time
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import spotipy.util as util
import random
import json
import sys
import webbrowser
import uuid
from flask_session import Session
import os
import pandas as pd
import requests
import subprocess

debug = True

class Song:
    def __init__(self, name, artist, album, album_id, play_count, sound_clip, image):
        self.name = name
        self.artist = artist
        self.album = album
        self.album_id = album_id
        self.play_count = play_count
        self.sound_clip = sound_clip
        self.image = image
    
    def update_play_count(self):
        self.play_count = self.get_play_count()
        return self

    def get_play_count(self):      
        r = requests.get(f"https://api.t4ils.dev/albumPlayCount?albumid={self.album_id}").json()   # gets all the metatdata from the public API
        album_discs = r['data']['discs']    # list of album discs
        for disc in album_discs:            # goes thru each disc
            album_tracks = disc['tracks']   # gets list of song on a disc
            for track in album_tracks:      # goes thru each song in the list
                if track['name'] == self.name:
                    return track['playcount']
        return -1

class Playlist:
    def __init__(self, name, id):  
        self.id = id
        self.name = name
        self.songs = []

    def populate(self, sp):
        tracks = get_all_playlist_tracks(playlist_id_in=self.id, sp = sp)
        for song in tracks:
            temp_name = song['track']['name']
            temp_artist = song['track']['artists'][0]['name']
            temp_album = song['track']['album']['name']
            temp_album_id = song['track']['album']['id']
            temp_play_count = 0
            temp_clip = song['track']['preview_url']
            temp_image = song['track']['album']['images'][0]['url']
            self.songs.append(Song(temp_name, temp_artist, temp_album, temp_album_id, temp_play_count, temp_clip, temp_image))
        
    def toJson(self):
        return json.dumps(self, default=lambda o: o.__dict__)
    
    def size(self):
        return len(self.songs)

def get_all_playlist_tracks(playlist_id_in, sp):
    if playlist_id_in == 'liked_songs':
        results = sp.current_user_saved_tracks()
    else:
        results = sp.user_playlist_tracks(playlist_id = playlist_id_in)
    tracks = results['items']
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])
    return tracks

def create_playlists(sp):
    lists = sp.current_user_playlists()['items']
    ret_pls = []
    for playlist in lists:
        ret_pls.append(Playlist(playlist['name'], playlist['id']))
    ret_pls.append(Playlist("Liked Songs", "liked_songs"))
    return ret_pls

def playlist_to_id(pls, id):
    for pl in pls:
        if(pl.id == id):
            return pl
    return None

def create_playlist(sp, id):
    if id == "liked_songs":
        return Playlist("Liked Songs", "liked_songs")
    pl = sp.playlist(id)
    return Playlist(pl['name'], pl['id'])


client_id = os.environ.get('SPOTIFY_CLIENT_ID')
client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
scope = "user-library-read playlist-read-private playlist-read-collaborative"

if debug:
    redirect_uri = 'http://localhost:5000'
else:
    redirect_uri = 'https://playlistbattle.herokuapp.com'


#CREATE SERVER
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(64)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './.flask_session/'
Session(app)

# set up cache folder stuff
caches_folder = './.spotify_caches/'
if not os.path.exists(caches_folder):
    os.makedirs(caches_folder)

def session_cache_path():
    return caches_folder + session.get('uuid')

@app.route('/')
def index():
    if not session.get('uuid'):
        session['uuid'] = str(uuid.uuid4())

    auth_manager = spotipy.oauth2.SpotifyOAuth(scope='user-library-read playlist-read-private playlist-read-collaborative',
                                                client_id = client_id,
                                                client_secret = client_secret,
                                                redirect_uri = redirect_uri,
                                                cache_path=session_cache_path(), 
                                                show_dialog=True)
    if request.args.get("code"):
        auth_manager.get_access_token(request.args.get("code"))
        return redirect('/')
    
    if not auth_manager.get_cached_token():
        auth_url = auth_manager.get_authorize_url()
        return render_template("index.html", auth_url = auth_url)
    
    sp = spotipy.Spotify(auth_manager=auth_manager)
    access_token = auth_manager.get_access_token()['access_token']
    return redirect(url_for('choose', access_token = access_token))


    
# Choose Screen: Where you choose which playlist to select
@app.route('/choose/<access_token>', methods = ['GET', 'POST'])
def choose(access_token): 
    sp = spotipy.Spotify(auth = access_token)
    score = -1
    playlists = create_playlists(sp)
    seed = int(round(time.time() * 1000))
    return render_template('choose.html', playlists = playlists, name = sp.me()['display_name'], access_token = access_token, seed = seed)

# Game Screen: Where one instance of the game is
@app.route('/game/<access_token>/<pl_id>/<int:seed>/<int:song_counter>/<int:score>/<int:pl_made>', methods = ['GET', 'POST'])
def game(access_token, pl_id, song_counter, score, pl_made, seed):
    sp = spotipy.Spotify(auth = access_token)
    if pl_id == 'none':
        pl_id = request.form.get('action')
    chosen_playlist = create_playlist(sp, pl_id)
    chosen_playlist.populate(sp)
    random.Random(seed).shuffle(chosen_playlist.songs) # shuffle playlist the same way using the generated seed
    if song_counter+1 < chosen_playlist.size():
        song1 = chosen_playlist.songs[song_counter].update_play_count()
        song2 = chosen_playlist.songs[song_counter+1].update_play_count()
    else:
        return render_template("win.html", access_token = access_token)
    return render_template('game.html', playlist = chosen_playlist, song1 = song1, song2 = song2, pl_id = pl_id,
        score = score, song_counter = song_counter, access_token = access_token, seed = seed)

# Restart Function: returns a redirect to the game screen
@app.route('/restart/<access_token>/<pl_id>', methods = ['GET', 'POST'])
def restart(access_token, pl_id):
    seed = int(round(time.time() * 1000))
    return redirect(f"/game/{access_token}/{pl_id}/{seed}/0/0/1")

# Sign out function, returns a redirect to the sign in screen
@app.route('/sign_out')
def sign_out():
    os.remove(session_cache_path())
    try:
        # Remove the CACHE file (.cache-test) so that a new user can authorize.
        os.remove(session_cache_path())
    except OSError as e:
        print ("Error: %s - %s." % (e.filename, e.strerror))
    session.clear()
    return redirect('/')

# Runs the app
if __name__ == "__main__":
    app.run()