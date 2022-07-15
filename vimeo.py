#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import requests

from json import loads as jl, dumps as jd

class Arguments():
	""" argparse wrapper, to reduce code verbosity """
	__parser = None
	__args = None

	def __init__(self, args, **kwargs):
		import argparse
		self.__parser = argparse.ArgumentParser(**kwargs)
		for arg in args:
			self.__parser.add_argument(*arg[0], **arg[1])
		self.__args = self.__parser.parse_args()

	def help(self):
		self.__parser.print_help()

	def __getitem__(self, name):
		return self.__getattr__(name)

	def __getattr__(self, name):
		ret = getattr(self.__args, name)
		if isinstance(ret, list) and (1 == len(ret)):
			ret = ret[0]
		return ret

def findTags(tag, html):
	return [dict(re.findall(r'(\S+)="([^"]*)"', x)) for x in re.findall(r'(<' + tag + r'\s[^>]+>)', html)]

def rebuildStream(id, url):
	cdn = re.match(r'^(.*?/video/)(.*?)(/audio/.*)$', url)
	(dest, videos, audios) = cdn.groups()
	if id not in videos:
		print('Error detecting highest quality video from the streams, aborting')
		exit(6)
	return dest + id + audios

def first(o):
	cdns = list(o.values())
	return cdns[0]

def parse_m3u8(url):
	def parseLine(text):
		d = {}
		text = text.strip()
		while len(text) > 0:
			match = re.match(r'\s*([^=]+?)\s*=\s*', text)
			id = match.group(1)
			text = text[len(match.group(0)):]

			match = re.match(r'"\s*([^"]*?)\s*"\s*(?:,\s*|$)' if text[0] == '"' else r'(.*?)\s*(?:,\s*|$)', text)
			value = match.group(1)
			text = text[len(match.group(0)):]

			d[id.lower()] = value
		return d
	def uri_to_url(uri):
		backs = int(len(re.match(r'^((../)*)', uri).group(1) or '') / 3)
		return '/'.join(url.split('/')[:-backs-1]) + '/' + uri[backs*3:]

	response = requests.get(url)
	if (response.status_code != 200):
		print('Unable to download the playlist')
		exit(7)

	streams = { 'video': [], 'audio': [], 'subs': [] }
	text = response.text.split('\n')
	i = 0
	while i < len(text):
		if text[i].startswith('#EXT-X-MEDIA'):
			info = parseLine(text[i][13:])
			if not info:
				continue
			if (info['type'].lower() == 'audio'):
				info['url'] = uri_to_url(info['uri'])
				streams['audio'].append(info)
			elif (info['type'].lower() == 'subtitles'):
				info['url'] = uri_to_url(info['uri'])
				streams['subs'].append(info)
			else:
				print('Found unknown type: {}'.format(info['type']))
		elif text[i].startswith('#EXT-X-STREAM-INF'):
			info = parseLine(text[i][18:])
			if not info:
				continue
			while True:
				i += 1
				uri = text[i].strip()
				if uri:
					break
			info['url'] = uri_to_url(uri)
			streams['video'].append(info)
		i += 1
	return streams

def analyze(url):
	response = requests.get(url)
	if (response.status_code != 200):
		print('Failed to download the URL content')
		exit(1)

	# Find the `<link>`s that contain the information about the video stream
	links = findTags('link', response.text)
	embed = [x for x in links if 'type' in x and x['type'] == 'application/json+oembed']
	if (not embed):
		print('Unable to find the embeds for the video')
		exit(2)
	response = requests.get(embed[0]['href'])
	if (response.status_code != 200):
		print('Failed to download the embed manifest')
		exit(3)
	embed = jl(response.text)

	# Find the iframe player
	iframe = findTags('iframe', embed['html'])
	if (not iframe):
		print('Failed to find the iframed player')
		exit(4)
	iframe = iframe[0]

	# Extract stream information
	title = iframe['title']
	response = requests.get(iframe['src'])
	if (response.status_code != 200):
		print('Unable to download the player')
		exit(5)
	data = jl(re.search(r'var config\s*=\s*(.*?);\s*if\s*\(!config', response.text, re.DOTALL).group(1))
	dash = data['request']['files']['dash']
	hls  = data['request']['files']['hls']

	# Find the highest stream quality
	streams = {int(x['quality'][:-1]): x for x in dash['streams']}
	quality = [x for x in streams.keys()]
	quality.sort(reverse=True)
	topQualityStream = streams[quality[0]]
	tqsId = topQualityStream['id'][:8]

	# Grab the playlist
	m3u8 = parse_m3u8(rebuildStream(tqsId, first(hls['cdns'])['url']))

	print('{} [{}@{}]'.format(title, topQualityStream['quality'], topQualityStream['fps']))
	parsed = { 'audio': [], 'subs': [] }
	for video in m3u8['video']:
		audio = [x for x in m3u8['audio'] if x['group-id'] == video['audio']][0]
		subs = [x for x in m3u8['subs'] if x['group-id'] == video['subtitles']][0]
		parsed['audio'].append(audio['group-id'])
		parsed['subs'].append(subs['group-id'])
		print('Video [{}, {}@{}]: {}'.format(video['codecs'], video['resolution'], video['frame-rate'], video['url']))
		print('* Audio [{}ch]: {}'.format(audio['channels'], audio['url']))
		print('* Subtitles [{} {}]: {}'.format(subs['name'], subs['language'], subs['url']))
	print('\nDownload and rebuild with: ffmpeg.exe -i master.mp4 -i playlist.mp4 -c copy -map 0:v:0 -map 1:a:0 combined.mp4')

	# List unparsed streams
	unparsed = [x for x in m3u8['audio'] if x['group-id'] not in parsed['audio']]
	if unparsed:
		print('\nUnparsed audio streams:\n{}'.format(jd(unparsed, indent=2)))
	unparsed = [x for x in m3u8['subs'] if x['group-id'] not in parsed['subs']]
	if unparsed:
		print('\nUnparsed subtitle streams:\n{}'.format(jd(unparsed, indent=2)))

if __name__ == '__main__':
	args = Arguments(
		[
			[
				[],
				{
					'type': str,
					'nargs': 1,
					'metavar': 'URL',
					'help': 'URL to the accessible Vimeo video',
					'dest': 'url',
				}
			],
		],
		description='Grabs the highest definition quality streams off vimeo DASH playlists'
	)
	analyze(args.url)
