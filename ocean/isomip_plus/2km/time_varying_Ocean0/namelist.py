import warnings


def update_namelist(filename, config, warn=False):
    with open(filename) as f:
        namelist = [line.rstrip() for line in f]

    for key in config:
        found = False
        new_namelist = []
        for index, line in enumerate(namelist):
            if key in line:
                index = line.find(' = ')
                if index >= 0:
                    found = True
                    line = '{} = {}'.format(line[0:index], config[key])
            new_namelist.append(line)
        namelist = new_namelist

        if not found and warn:
            warnings.warn('{} not found in {}'.format(key, filename))

    with open(filename, 'w') as f:
        for line in namelist:
            f.write('{}\n'.format(line))
