import json

# json1_file = open('document.json')
# json1_str = json1_file.read()
# print(json1_str)
# json1_data = json.loads(json1_str)
# print(json1_data)
# print(type(json1_data))
# datapoints = json1_data['DEVICE_ID']
# print(datapoints)

print(json.loads(open('configs.json').read()))