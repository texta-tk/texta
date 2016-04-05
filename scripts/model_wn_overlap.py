import gensim
from sys import argv,exit
from collections import defaultdict
import codecs

MIN_FREQ = 100

if len(argv) == 1:
    print "Usage: python model_wn_overlap.py <model/file/path> <output/distribution/path>"
    exit(1)

model = gensim.models.Word2Vec.load(argv[1])

vocab = model.vocab

wn_word_file = "lit_pos_synidx.txt"

pos_counter = defaultdict(int)

matches = []

with codecs.open(wn_word_file,'r','utf-8') as fin:
    for line in fin:
	line = line.strip().split(':')
	if line[0].encode('utf-8') in vocab:
	    entry = vocab[line[0].encode('utf-8')]
	    if entry.count >= MIN_FREQ:
		pos_counter[line[1]]+=1
		matches.append((line[0],line[1],entry.count))

total = 0    
for pos in pos_counter:
    print "PoS[%s] = %d"%(pos,pos_counter[pos])
    total+= pos_counter[pos]
    
print
print "Total = %d"%total

matches.sort(key=lambda x: x[2],reverse=True)

with codecs.open(argv[2],'w','utf-8') as fout:
    fout.write('\n'.join(["%s:%d"%(match[0],match[2]) for match in matches if match[1] == 'n']))