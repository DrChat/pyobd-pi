FILE_BASELINE = 'baseline.csv'
FILE_DIFF = 'locktest.csv'

f_baseline = open(FILE_BASELINE)
f_diff = open(FILE_DIFF)

# assert headers equal
assert f_baseline.readline() == f_diff.readline()

# Parses all data from a file
def parse_file(file):
  b = []

  for line in file:
    line = line.split(',') # split by comma
    str_data = line[1]
    if str_data[0] == '"':
      str_data = str_data[1:-1] # strip quotes
    str_data = str_data.strip()

    str_bytes = str_data.split(' ')
    raw_bytes = [int(x, 16) for x in str_bytes]
    b.append(raw_bytes)
  
  return b

base = parse_file(f_baseline)
diff = parse_file(f_diff)

base_id_tab = {}
for b in base:
  if not b[0] in base_id_tab:
    base_id_tab[b[0]] = 1
    continue
  
  base_id_tab[b[0]] += 1

print("Base IDs and occurrences")
for id, occ in sorted(base_id_tab.items()):
  print(("%.3X: %d" % (id, occ)))

diff_id_tab = {}
for b in diff:
  if not b[0] in diff_id_tab:
    diff_id_tab[b[0]] = 1
    continue
  
  diff_id_tab[b[0]] += 1

print("Diff IDs and occurrences")
for id, occ in sorted(diff_id_tab.items()):
  print(("%.3X: %d" % (id, occ)))