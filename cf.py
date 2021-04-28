#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from optparse import *
import os.path
import re
import subprocess
import sys
import time
import urllib.request, urllib.error, urllib.parse

from lxml import etree
from markdownify import markdownify as md


CODEFORCES_URL = 'http://codeforces.com'
EPS = 1e-6


class Executer(object):
    def __init__(self, env, id):
        self.env = env
        self.id = id

    def compile(self):
        if len(self.env['compile']) == 0:
            return 0
        return subprocess.call(self.env['compile'].format(self.id), shell=True)

    def execute(self):
        return subprocess.Popen(
            self.env['execute'].format(self.id),
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE
        )


def add_options():
    usage = '%prog [options] [source code]'
    parser = OptionParser(usage=usage)
    parser.add_option('-c', '--contest', dest='contest_id',
                      help="Download the specific contest. \
                              If the PROBLEM_ID isn't specific, \
                              then download all problems in the contest.")
    parser.add_option('-p', '--problem', dest='problem_id',
                      help='Download the specific problem. \
                              The CONTEST_ID is required.')
    return parser.parse_args()


def install_proxy():
    if hasattr(conf, 'HTTP_PROXY'):
        proxy = urllib.request.ProxyHandler({'http': conf.HTTP_PROXY})
        opener = urllib.request.build_opener(proxy)
        urllib.request.install_opener(opener)


def download_contest(contest_id):
    contest_url = '/'.join((CODEFORCES_URL, 'contest', contest_id))
    contest_page = urllib.request.urlopen(contest_url)
    tree = etree.HTML(contest_page.read())
    for i in tree.xpath(
            ".//table[contains(@class, 'problems')]"
            "//td[contains(@class, 'id')]/a"):
        download_problem(contest_id, i.text.strip())


def download_problem(contest_id, problem_id):
    node_to_string = lambda node: node.text + ''.join(
                                  (etree.tostring(n, encoding='unicode',
                                                  method='text')
                                     for n in node.getchildren()))

    problem_url = '/'.join(
        (CODEFORCES_URL, 'contest', contest_id, 'problem', problem_id))
    problem_page = urllib.request.urlopen(problem_url)
    tree = etree.HTML(problem_page.read())
    description = md(etree.tostring(tree.xpath('.//div[contains(@class, "problem-statement")]')[0], pretty_print=True))
    title = tree.xpath(
        './/div[contains(@class, "problem-statement")]'
        '/div/div[contains(@class, "title")]')[0].text
    problem_name = title[3:].strip()

    basefname = conf.PATTERN.format(
        id=problem_id, name=problem_name, contest=contest_id)
    basefname = re.sub(
        r'upper\((.*?)\)', lambda x: x.group(1).upper(), basefname)
    basefname = re.sub(
        r'lower\((.*?)\)', lambda x: x.group(1).lower(), basefname)
    basefname = basefname.replace(' ', conf.REPLACE_SPACE)
    filename = basefname + conf.EXTENSION

    dirname = ''
    if hasattr(conf, 'CREATE_DIRECTORY_PER_PROBLEM') and \
       conf.CREATE_DIRECTORY_PER_PROBLEM:
        dirname = contest_id+"/"+problem_id
        os.makedirs(name=dirname, exist_ok=True)

    with open(os.path.join(dirname, filename), 'w') as f:
        for (input_node, answer_node) in zip(
                tree.xpath('.//div[contains(@class, "input")]/pre'),
                tree.xpath('.//div[contains(@class, "output")]/pre')):
            f.write('<input>\n')
            f.write(node_to_string(input_node).replace('<br/>', '\n'))
            f.write('\n')
            f.write('</input>\n')
            f.write('<answer>\n')
            f.write(node_to_string(answer_node).replace('<br/>', '\n'))
            f.write('\n')
            f.write('</answer>\n')

    if hasattr(conf, 'EXTRACT_INDIVIDUAL_TEST') and \
       conf.EXTRACT_INDIVIDUAL_TEST:
        test_num = 0
        for (input_node, answer_node) in zip(
                tree.xpath('.//div[contains(@class, "input")]/pre'),
                tree.xpath('.//div[contains(@class, "output")]/pre')):
            test_num += 1
            filename = basefname + str(test_num) + '.in'
            with open(os.path.join(dirname, filename), 'w') as f:
                 f.write(node_to_string(input_node).replace('<br/>', '\n').lstrip('\n'))

    if hasattr(conf, 'EXTRACT_DESCRIPTION') and \
       conf.EXTRACT_DESCRIPTION:
        
            filename = basefname + 'description.md'
            with open(os.path.join(dirname, filename), 'w') as f:
                 f.write(description.replace('<br/>', '\n').lstrip('\n'))

    print('contest={0!r}, id={1!r}, problem={2!r} is downloaded.'.format(
        contest_id, problem_id, problem_name))


def is_integer(s):
    try:
        int(s)
    except ValueError:
        return False
    return True


def is_number(s):
    try:
        float(s)
    except ValueError:
        return False
    return True


def floating_equal(a, b):
    return abs(a-b) < EPS


def check_result(answer_text, output_text):
    answer_tokens = answer_text.split()
    output_tokens = output_text.split()
    if len(answer_tokens) != len(output_tokens):
        return False
    for answer_token, output_token in zip(answer_tokens, output_tokens):
        if is_integer(answer_token) and is_integer(output_token):
            if int(answer_token) != int(output_token):
                return False
        elif is_number(answer_token) and is_number(output_token):
            if not floating_equal(float(answer_token), float(output_token)):
                return False
        else:
            if answer_token != output_token:
                return False
    return True


def handle_test(executer, case, input_text, answer_text):
    print('output:')
    start = time.time()
    proc = executer.execute()
  # os.set_blocking(proc.stdout.fileno(), False)
    proc.stdin.write(input_text.encode())
    if not input_text.endswith('\n'):
        proc.stdin.write('\n'.encode())
    proc.stdin.flush()
    proc.stdin.close()
    output_text = ''
    for output_line in proc.stdout:
        line = output_line.decode('UTF-8')
        print(line)
        output_text += line
    proc.wait()
    output_text = output_text.rstrip('\n')
    end = time.time()

    if proc.returncode != 0:
        result = 'RE'
    elif answer_text == output_text:
        result = 'EXACTLY'
    elif check_result(answer_text, output_text):
        result = 'AC'
    else:
        result = 'WA'

    if result != 'EXACTLY':
        print('answer:')
        print(answer_text)

    print('=== Case #{0}: {1} ({2} ms) ===\n'.format(
        case, result, int((end-start) * 1000)))
    if result != 'EXACTLY':
        input('press enter to continue or <C-c> to leave.')


def main():
    global options, conf
    (options, args) = add_options()

    try:
        import conf
    except ImportError as e:
        print('conf.py does not exist.')
        print('Maybe you should copy `conf.py.example` to `conf.py`.')
        sys.exit(1)

    if options.contest_id is not None:
        install_proxy()
        if options.problem_id is not None:
            download_problem(options.contest_id, options.problem_id)
        else:
            download_contest(options.contest_id)
        sys.exit(0)

    if len(args) < 1:
        print('Missing command line argument')
        sys.exit(1)

    if not os.path.exists(args[0]):
        print('Source code does not exist!')
        sys.exit(1)

    id, lang = os.path.splitext(args[0])
    executer = Executer(conf.ENV[lang], id)

    ret = executer.compile()

    if ret != 0:
        print('>>> Failed to compile the source code!')
        sys.exit(1)

    with open('{0}{1}'.format(id, conf.EXTENSION)) as test_file:
        samples = etree.fromstring(
            '<samples>{0}</samples>'.format(test_file.read()))
        nodes = samples.getchildren()
        for case in range(len(nodes)//2):
            input_text = nodes[case*2].text[1:-1]
            answer_text = nodes[case*2+1].text[1:-1]
            handle_test(executer, case, input_text, answer_text)

if __name__ == '__main__':
    main()
