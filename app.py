from flask import Flask, render_template, request, redirect
# from flask_sqlalchemy import SQLAlchemy
import datetime
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pylast
import random
import json

#global things
global playlists

#Spotify API STUFF
def authorize_spotify():
    client_id_in = '379b15e111a14089ae41a384d0db80a2'
    client_secret_in = 'f487fb0030f640eabf35f5ceefffe427'
    redirect_uri_in = 'https://jarrettbierman.github.io/'
    scope = "user-library-read playlist-read-private playlist-read-collaborative"

    auth_manager_in = SpotifyOAuth(client_id = client_id_in, client_secret = client_secret_in, redirect_uri = redirect_uri_in, scope=scope, username='jarrettbierman')
    sp = spotipy.Spotify(auth_manager=auth_manager_in)
    return sp

    print("Spotify has been authorized")


#LAST-FM-API-STUFF
def authorize_lastfm():
    API_KEY = '2296dec001d131f586bd715159105fb0'
    API_SECRET = '7f57826cbedd327ffee7f0ebcaf6c7b9'
    user_name = 'jarrettbierman'
    user_password = pylast.md5('Beerbottle711!')
    network = pylast.LastFMNetwork(api_key=API_KEY, api_secret=API_SECRET, username=user_name, password_hash=user_password)
    return network



class Song:
    def __init__(self, name, artist, album, play_count, sound_clip):
        self.name = name
        self.artist = artist
        self.album = album
        self.play_count = play_count
        self.sound_clip = sound_clip

    def update_play_count(self):
        self.play_count = network.get_track(self.artist, self.name).get_playcount()
        print("count updated")
        return self

class Playlist:
    def __init__(self, name, id): # playlist_object will be something like sp_id = sp.current_user_playlists()['items'][0]['id']  p_obj = sp.user_playlist_tracks(playlist_id = p_id)  
        self.id = id
        self.name = name
        self.songs = []

    def populate(self):
        # results = sp.user_playlist_tracks(playlist_id = self.id)
        # tracks = results['items']
        tracks = get_all_playlist_tracks(playlist_id_in=self.id)
        for song in tracks:
            temp_name = song['track']['name']
            temp_artist = song['track']['artists'][0]['name']
            temp_album = song['track']['album']['name']
            # temp_play_count = network.get_track(temp_artist, temp_name).get_playcount()
            temp_play_count = 0
            temp_clip = song['track']['preview_url']
            self.songs.append(Song(temp_name, temp_artist, temp_album, temp_play_count, temp_clip))
 

        # randomize list of songs
        random.shuffle(self.songs)
        
    def toJson(self):
        return json.dumps(self, default=lambda o: o.__dict__)

def get_all_playlist_tracks(playlist_id_in):
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
    # for pl in ret_pls:
    #     print(f"Name: {pl.name} id: {pl.id}")
    return ret_pls

def playlist_to_id(pls, id):
    for pl in pls:
        if(pl.id == id):
            return pl
    return None


#FLASK SERVER STUFF
app = Flask(__name__)

# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
# db = SQLAlchemy(app)

# class Score(db.Model):
#     name = db.Column(db.String(100), nullable=False)
#     score = db.Column(db.Integer, primary_key=True)
#     # date_created = db.Column(db.DateTime, defalult=datetime.utcnow)

#     def __repr__(self):
#         return '<Task %r>' % self.id

sp = authorize_spotify()
network = authorize_lastfm()
playlists = create_playlists(sp)
chosen_playlist = None
song_counter = 0
score = -1

#THE ACTUAL SERVER PART
@app.route('/', methods = ['GET', 'POST'])
def index(): 
    global score
    global song_counter
    global chosen_playlist    
    score = -1
    song_counter = 0
    chosen_playlist = None
    return render_template('index.html', playlists = playlists)

@app.route('/game', methods = ['GET', 'POST'])
def game():
    # if(request.method == 'POST'):
    #     return "hi"
    # else:
    global chosen_playlist    
    global song_counter
    global score

    if(chosen_playlist == None):
        chosen_playlist_id = request.form['action'] # action form, the name of the playlist
        chosen_playlist = playlist_to_id(playlists, chosen_playlist_id)
        chosen_playlist.populate()
    if(song_counter < len(chosen_playlist.songs)):
        song1 = chosen_playlist.songs[song_counter].update_play_count()
        song2 = chosen_playlist.songs[song_counter+1].update_play_count()
        song_counter += 1
        score += 1
    return render_template('game.html', playlist = chosen_playlist, song1 = song1, song2 = song2, score = score)

@app.route('/restart', methods = ['GET', 'POST'])
def restart():
    global song_counter
    global score
    song_counter = 0
    score = -1
    random.shuffle(chosen_playlist.songs)
    return game()

if __name__ == "__main__":
    app.run(debug = True)