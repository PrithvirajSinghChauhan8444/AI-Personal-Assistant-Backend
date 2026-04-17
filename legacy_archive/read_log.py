try:
    with open('verification_output_safe.txt', 'r', encoding='utf-16') as f:
        print(f.read().replace('\r', '\n'))
except Exception as e:
    print(f"UTF-16 failed: {e}")
    try:
        with open('verification_output_safe.txt', 'r', encoding='utf-8', errors='ignore') as f:
            print(f.read().replace('\r', '\n'))
    except Exception as e2:
        print(f"UTF-8 failed: {e2}")
