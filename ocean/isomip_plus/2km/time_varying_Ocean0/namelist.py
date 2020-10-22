import warnings


def update_namelist(filename, config):
    with open(filename) as f:
        namelist = [line.rstrip() for line in f]

    for key in config:
        found = False
        for index, line in enumerate(namelist):
            if key in line:
                index = line.find(' = ')
                if index >= 0:
                    found = True
                    namelist[index] = \
                        '{} = {}'.format(line[0:index], config[key])

        if not found:
            warnings.warn('{} not found in {}'.format(key, filename))

    with open(filename, 'w') as f:
        for line in namelist:
            f.write('{}\n'.format(line))
