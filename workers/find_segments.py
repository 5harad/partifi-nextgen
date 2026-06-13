from PIL import Image, ImageDraw
from numpy import argmin, asarray, ceil, concatenate, cumsum, diff, mean, nonzero, var
import argparse
import random
import os
import sys
import db_conn
import re

from pipeline.cut_segments import default_pool_size
from pipeline.parallel import map_in_parallel

def update_db(partset_id, imfile, rotation, margins, segments):
	match = re.search(r"page-(\d+)", imfile)
	if not match:
		return
	page = int(match.group(1))
	db_conn.execute(
		"INSERT INTO pages (partset_id, page, left_margin, right_margin, rotation) "
		"VALUES (:partset_id, :page, :left, :right, :rotation)",
		{"partset_id": partset_id, "page": page, "left": margins[0], "right": margins[1], "rotation": rotation},
	)
	if len(segments) > 1:
		for ndx in range(len(segments) - 1):
			db_conn.execute(
				"INSERT INTO segments (partset_id, page, top, bottom) VALUES (:partset_id, :page, :top, :bottom)",
				{"partset_id": partset_id, "page": page, "top": segments[ndx], "bottom": segments[ndx + 1]},
			)

# smooth the input x via a moving average with reflection at the boundries
# window_len should be an odd integer
def smooth(x, window_len):
	if len(x) < window_len:
		raise ValueError('Input vector needs to be bigger than window size')
	if window_len < 3:
		return x
	
	k = window_len // 2
	x = concatenate(([0], x[k:0:-1], x, x[-2:-k-2:-1]))
	cumsum_x = cumsum(x)
	s = [float(cumsum_x[i+k]-cumsum_x[i-k-1])/window_len for i in range(k+1,len(x)-k)]
	
	return s
	
# determine the skew of the image, searching over the specified degree range
def find_skew(im, search_center=0, search_radius=5):
	if search_radius <= 0:
		raise ValueError('search radius must be positive')
	# determine the rotation angles over which to search, either coarse or fine 
	# depending on the search radius
	if search_radius < 1:
		lwr = -int(ceil(search_radius/0.1))
		upr = -lwr + 1
		degs = [x*.1 + search_center for x in range(lwr,upr)]
	else:
		lwr = -int(ceil(search_radius))
		upr = -lwr + 1
		degs = [x + search_center for x in range(lwr,upr)]
	
	# rotate the image through various angles, and for each angle compute 
	# variance in the row darkness. Variance should be maximized when 
	# the image is correctly aligned.
	width, height = im.size
	argmax_var, max_var = 0, 0
	for deg in degs:
		rotated_im = im.rotate(deg, Image.BILINEAR)		
		pixels = asarray(rotated_im)
		row_lightness = mean(pixels,1)
		v = var(row_lightness)
		
		if v > max_var:
			argmax_var = deg
			max_var = v
						
	# if this was a coarse search, recursively call find_skew centered
	# around the coarse optimum
	if search_radius < 1:
		if argmax_var == 0:
			return 0.0
		else:
			return -argmax_var
	else:
		return find_skew(im, argmax_var, 0.5)	
		
def find_segments(imfile, fixskew=False):
	# convert image to grayscale
	im = Image.open(imfile).convert('L')
	width, height = im.size

	# if requested, detect and correct image skew
	skew = 0
	if fixskew:
		small_im = im.resize((width // 4, height // 4), Image.LANCZOS)
		skew = find_skew(small_im)
		mask = Image.new('L', im.size, 255)
		rotated_im = Image.new('L', im.size, 255)
		rotated_im.paste(im.rotate(-skew, Image.BILINEAR), mask.rotate(-skew))
		im = rotated_im
		
	# compute (smoothed) darkness of each row and column
	window_len = 2 * (height // 200) + 1
	pixels = asarray(im)
	pixels = 1 - pixels/255.
	row_darkness = mean(pixels,1)
	row_darkness = smooth(row_darkness, window_len)
	col_darkness = mean(pixels,0)
	col_darkness = smooth(col_darkness, window_len)
	bg_darkness = mean(row_darkness)
	
	# identify the left/right margins by looking for the first/last relatively dark columns
	dark_cols = nonzero(col_darkness > (bg_darkness*1.1))[0]
	if len(dark_cols) > 0:
		page_left = min(dark_cols) - window_len
		page_left = min(width // 5, max(width // 20, page_left))
		page_right = max(dark_cols) + window_len
		page_right = max(4 * width // 5, min(19 * width // 20, page_right))
		margins = [page_left, page_right]
	else:
		margins = [width // 20, 19 * width // 20]
	
	# identify the top/bottom of the page (excluding titles and page numbers) by looking 
	# for the first/last relatively dark regions
	cum_darkness = cumsum(row_darkness)
	region_size = height // 40
	region_darkness = (cum_darkness[region_size:]-cum_darkness[:-region_size])/region_size
	dark_regions = nonzero(region_darkness > (bg_darkness*1.1))[0]
	if len(dark_regions) > 0:
		page_top = min(dark_regions)
		page_top = max(height // 20, page_top)
		page_bottom = max(dark_regions) + region_size
		page_bottom = min(height * 19 // 20, page_bottom)
	else:
		page_top = height // 20
		page_bottom = height * 19 // 20
		
	# find local minima (including one-sided minima) that are relatively white
	# and that are between the page boundaries
	segments = [r for r in range(max(1,page_top), page_bottom) if
		row_darkness[r] <= min(row_darkness[r-1:r+2]) 
		and row_darkness[r] < max(row_darkness[r-1:r+2])
		and row_darkness[r] < bg_darkness]
	if page_top > 0:
		segments.insert(0, page_top)
	if page_bottom < height:
		segments.append(page_bottom)
			
	# iteratively adjust segments that are unusally close together
	sep = diff(segments)
	if len(segments) == 2:
		segments = [height // 10, height * 9 // 10]
	else:
		ndx = argmin(sep)
		while sep[ndx] < max(mean(sep) / 2, height // 50) and len(segments) >= 3:
			segments[ndx] += argmin(row_darkness[segments[ndx]:segments[ndx+1]+1])
			del segments[ndx+1]
			sep = diff(segments)
			ndx = argmin(sep)

	# generate at most 30 segments
	if len(segments) > 30:
		segments = random.sample(segments, 30)

	# normalize segment positions and left/right margins as a percentage of height
	norm_segments = [round(100*float(s)/height,1) for s in segments]
	norm_margins = [round(100*float(m)/width,1) for m in margins]

	return imfile, skew, norm_margins, norm_segments
	
# helper function to deal with a single tuple of arguments
def find_segments_star(args):
	return find_segments(*args)
	
# parallel segmentation — workers compute only; DB writes stay in the parent process
def par_find_segments(imfiles, fixskew, partset_id=None):
	args = list(zip(imfiles, [fixskew] * len(imfiles)))
	workers = default_pool_size(len(args))
	results = map_in_parallel(find_segments_star, args, workers=workers)

	if partset_id:
		num_tasks = len(imfiles)
		for i, (imfile, skew, norm_margins, norm_segments) in enumerate(results):
			update_db(partset_id, imfile, -skew, norm_margins, norm_segments)
			db_conn.execute(
				"UPDATE partsets SET analysis_progress = :progress WHERE id = :id",
				{"progress": 100.0 * (i + 1) / num_tasks, "id": partset_id},
			)

	return results
	
def draw_segments(imfile, skew, segments, margins):
	im = Image.open(imfile).convert('RGB')
	width, height = im.size
	
	# rotate the image
	mask = Image.new('L', im.size, 255)
	rotated_im = Image.new('RGB', im.size, (255,255,255))
	rotated_im.paste(im.rotate(-skew, Image.BILINEAR), mask.rotate(-skew))
	im = rotated_im
	
	draw = ImageDraw.Draw(im)
	
	# draw the left/right margins
	margins = [int(float(m)/100*width) for m in margins]
	draw.line((margins[0], 0, margins[0], height), fill=(255,0,0))
	draw.line((margins[1], 0, margins[1], height), fill=(255,0,0))
	
	# draw the horizontal segments
	segments = [int(float(s)/100*height) for s in segments]
	for s in segments:
		draw.line((0, s, width, s), fill=(255,0,0)) 
	
	return im	

def analyze_score(partset_id: str, imfiles: list[str]) -> None:
	if not imfiles:
		db_conn.execute(
			"UPDATE partsets SET status = 'analysis', analysis_start = NOW(), "
			"analysis_complete = NOW(), analysis_progress = 100 WHERE id = :id",
			{"id": partset_id},
		)
		return
	db_conn.execute(
		"UPDATE partsets SET status = 'analysis', analysis_start = NOW(), analysis_progress = 0 WHERE id = :id",
		{"id": partset_id},
	)
	par_find_segments(imfiles, False, partset_id)
	db_conn.execute(
		"UPDATE partsets SET analysis_complete = NOW(), analysis_progress = 100 WHERE id = :id",
		{"id": partset_id},
	)


def main():
	parser = argparse.ArgumentParser(description='Segment a music score')
	parser.add_argument('imfiles', metavar='imfile', nargs='+')
	parser.add_argument('--view', action='store_true')
	parser.add_argument('--fix-skew', dest='fixskew', action='store_true', default=False)
	parser.add_argument('--update-db', metavar='partset_id', dest='partset_id', default=None)
	args = parser.parse_args()
	
	# update the database if requested
	if args.partset_id:
		db_conn.execute("UPDATE partsets SET status = 'analysis', analysis_start = NOW() WHERE id = :id", {"id": args.partset_id})
		
	# parallel segmentation (DB updates happen inside par_find_segments when partset_id set)
	results = par_find_segments(args.imfiles, args.fixskew, args.partset_id)

	if args.partset_id:
		db_conn.execute(
			"UPDATE partsets SET analysis_complete = NOW(), analysis_progress = 100 WHERE id = :id",
			{"id": args.partset_id},
		)
			
	# output results
	for (imfile, skew, margins, segments) in results:
		fname = os.path.basename(imfile)
		print("\t".join(map(str, [fname, skew, margins, segments])))
		
	# if requested, display the segmented files
	if args.view:
		for (imfile, skew, margins, segments) in results:
			im = draw_segments(imfile, skew, segments, margins)
			im.show()

if __name__== '__main__':
	main()
