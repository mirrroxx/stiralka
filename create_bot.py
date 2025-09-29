time = []
left = 8
right = 0
for i in range(20):
    time.append((left, right))
    right += 35
    if right >= 60:
        left += 1
        right -= 60
    time.append((left, right))
print(time)