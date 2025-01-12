#!/usr/bin/env python
from signal import SIGINT, SIGKILL
import os
import re

from servicemanager import subprocess


def kill_pid(context, pid, force=False):

    if _is_system_or_smserver_or_test_process(pid):
        return "Not allowed to kill system, test or smserver process (pid = %d)" % pid

    try:
        if force:
            os.kill(pid, SIGKILL)
        else:
            os.kill(pid, SIGINT)

    except Exception, e:
        error = "Could not kill pid: " + str(pid) + " because of exception: " + str(e)
        context.log(error)
        return error


def _is_system_or_smserver_or_test_process(pid):

    if pid == 1:
        return True

    if _is_init_process(pid):
        return True

    if _is_smserver_process(pid):
        return True

    if _is_pytest_process(pid):
        return True

    if _is_pycharm_process(pid):
        return True

    if _is_pycharm_test_process(pid):
        return True

    if _is_pycharm_related_process(pid):
        return True

    return False


def _is_pid_in_list(pid, command):
    ps_command = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    ps_output = ps_command.stdout.read()
    ps_pid_str = ps_output.strip()
    for process in ps_pid_str.split("\n"):
        if process and int(process) == pid:
            return True
    return False

def _is_init_process(pid):
    command = "ps -eo ppid,pid,etime,rss,args | grep 'init --user' | grep -v 'grep init --user' | grep -v indicator | awk '{print $2 }'"
    return _is_pid_in_list(pid, command)


def _is_smserver_process(pid):
    command = "ps -eo pid,args | grep %d | grep 'smserver\.py' | awk '{print $1}'" % pid
    return _is_pid_in_list(pid, command)


def _is_pytest_process(pid):
    command = "ps -eo pid,args | grep %d | grep 'py\.test' | awk '{print $1}'" % pid
    return _is_pid_in_list(pid, command)


def _is_pycharm_test_process(pid):
    command = "ps -eo pid,args | grep %d | grep 'pytestrunner\.py' | awk '{print $1}'" % pid
    return _is_pid_in_list(pid, command)


def _is_pycharm_process(pid):
    command = "ps -eo pid,args | grep %d | grep 'pydevd\.py' | awk '{print $1}'" % pid
    return _is_pid_in_list(pid, command)


def _is_pycharm_related_process(pid):
    command = "ps -eo pid,args | grep %d | grep 'pycharm' | awk '{print $1}'" % pid
    return _is_pid_in_list(pid, command)


def kill_by_test_id(context, force):
    pids = _get_process_ids_for_test(context)
    services_killed = set()
    for pid in pids:
        service_name = _get_service_name_for_pid(pid)
        if force:
            if service_name:
                context.log("Force killing %s (pid: %s)" % (service_name, pid))    
            else:
                context.log("Force killing pid: %s (unknown/missing service name)" % pid)
        context.log("killing %s" % service_name)
        kill_pid(context, pid, force)
        if service_name:
            services_killed.add(service_name)

    return services_killed


def test_has_running_processes(context):
    return len(_get_process_ids_for_test(context)) > 0


def _get_process_ids_for_test(context):
    return _get_process_ids_for_processes_matching(re.escape("-Dservice.manager.testId=%s" % context.instance_id))


def _get_process_ids_for_processes_matching(regex):
    command = "ps -eo pid,args | grep '%s' |grep -v 'grep %s' |  awk '{print $1}'" % (regex, regex)
    ps_command = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    stdout, stderr = ps_command.communicate()

    return map(int, stdout.split("\n")[:-1])


def _get_service_name_for_pid(pid):
    command = "ps -p %s -o command,args" % pid

    ps_command = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    stdout, stderr = ps_command.communicate()
    ps_output = stdout.split()

    p = re.compile('-Dservice\.manager\.serviceName=([A-Z_]+)')

    for i in ps_output:
        t = p.match(i)
        if t:
            return t.group(1)

    return None


class SmProcess:

    def __init__(self, ppid, pid, uptime, mem, args):
        self.ppid = ppid
        self.pid = pid
        self.uptime = uptime
        self.mem = mem
        self.args = args

    @staticmethod
    def processes_matching(regex):
        command = "ps -eo ppid,pid,etime,rss,args | egrep -e '%s' | grep -vi 'grep -e'" % regex
        ps_command = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
        stdout, stderr = ps_command.communicate()
        ps_output = stdout.split("\n")[:-1]

        def process_line_to_object(process_line):
            values = process_line.strip().split()
            return SmProcess(int(values[0]), int(values[1]), values[2], values[3], values[4:])

        ret = map(process_line_to_object, ps_output)

        return ret

    def has_argument(self, argument):
        return argument in self.args

    def extract_argument(self, regex_with_group, default_if_none):
        regex = re.compile(regex_with_group)
        for arg in self.args:
            match = regex.match(arg)
            if match:
                return match.group(1)

        return default_if_none

    def extract_arguments(self, regex_with_group, default_if_none):
        regex = re.compile(regex_with_group)
        matches = []
        for arg in self.args:
            match = regex.match(arg)
            if match:
                matches += [match.group(1)]

        if matches:
            return ",".join(matches)

        return default_if_none

    def extract_integer_argument(self, regex_with_group, default_if_none):
        arg = self.extract_argument(regex_with_group, None)

        if arg:
            return int(arg)

        return default_if_none
