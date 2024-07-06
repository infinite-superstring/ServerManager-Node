import os.path
import asyncio

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from threading import Thread
from datetime import datetime
from uuid import uuid1

import subprocess
import time
import utils.websocket as websocket
from utils.logger import logger

class shellTaskUtils:
    __websocket: websocket
    __scheduler: BackgroundScheduler
    __process_list: dict[str: subprocess.Popen] = {}
    __process_mark: dict[str:str] = {}
    __get_process_thread: Thread = None

    def __init__(self, ws: websocket):
        """
        初始化节点任务工具
        """
        self.__websocket = ws
        self.__scheduler = BackgroundScheduler()

    def __del__(self):
        self.__scheduler.shutdown(wait=False)

    def init_task_list(self, task_list):
        """
        初始化节点任务列表

        执行类型:
        指定时间 -> 'date-time'
        周期 -> 'cycle'
        间隔 -> 'interval'

        数据格式 :
        [
            {
                name:名称,
                exec_type:执行类型,
                interval:间隔时间(秒),
                that_time:指定时间(时间戳),
                exec_count:执行次数(null 为 无限),
                cycle:{
                    time: 时间,
                    week:[] ->      1: 'monday',
                    },              2: 'tuesday',
                command:执行命令,     3: 'wednesday',
                                    4: 'thursday',
                                    5: 'friday',
                                    6: 'saturday',
                                    7: 'sunday',
            }
        ]

        """

        task = {
            "name": "task_name",  # 任务名
            "uuid": "uuid",  # 任务uuid
            "type": "task_type",  # 任务类型
            "exec_path": "/etc/sshd",  # 执行路径
            "shell": "cd xxxxxx",  # Shell脚本
            "time": 10000,  # 在任务类型为date-time时为目标时间戳，其他情况则为从0点开始的秒数
            'week': [1, 2, 3],  # 仅在任务类型为cycle时生效，代表以周为单位的时间
            "count": 5  # 执行次数
        }

        task_start = {  # 任务进程开始时
            'action': 'task:process_start',
            'data': {
                'uuid': "xxxxxxx",  # 任务uuid
                "mark": "xxxxxxx",  # 另一个UUID，用于标记进程
                "timestamp": 10000  # 任务开始时时间搓
            }
        }

        task_output = {  # 任务进程输出时
            'action': 'task:process_output',
            'data': {
                'uuid': "xxxxxxxx",  # 任务uuid
                "mark": "xxxxxxx",  # 另一个UUID，用于标记进程
                'line': "process_output"  # 进程输出
            }
        }

        task_stop = {  # 任务进程停止时
            'action': 'task:process_stop',
            'data': {
                'uuid': "xxxxxxxx",  # 任务uuid
                "mark": "xxxxxxx",  # 另一个UUID，用于标记进程
                'code': 0,  # 进程返回值，用于判断进程是否执行成功
                "timestamp": 10000  # 任务结束时时间搓
            }
        }

        for task in task_list:
            """
            uuid: str 任务唯一标识符
            exec_type: str 执行类型
            shell: str 执行的命令
            cwd: str 执行器目录
            exec_time: int 运行时间
            exec_cycle: dict 运行周期
            exec_count: 运行次数
            """
            self.__handle_start_task(
                uuid=task.get('uuid'),
                exec_type=task.get('type'),
                shell=task.get('shell'),
                cwd=task.get("exec_path"),
                exec_time=task.get('time'),
                exec_week=task.get('week'),
                exec_count=task.get('count')
            )
        self.__scheduler.start()

    def add_task(self, task):
        """添加任务"""
        task_uuid = task.get('uuid')
        if self.__scheduler.get_job(task_uuid):
            logger.warning(f"任务uuid: {task_uuid}已存在")
            return False
        self.__handle_start_task(
            uuid=task_uuid,
            exec_type=task.get('type'),
            shell=task.get('shell'),
            cwd=task.get("exec_path"),
            exec_time=task.get('time'),
            exec_week=task.get('week'),
            exec_count=task.get('count')
        )
        return True

    def remove_task(self, task_uuid):
        """使用UUID删除任务"""
        print(self.__scheduler.get_job(task_uuid))
        if not self.__scheduler.get_job(task_uuid):
            logger.warning(f"任务uuid: {task_uuid}不存在")
            return False
        self.__scheduler.remove_job(task_uuid)

    def reload_task(self, task):
        """重新载入一个任务"""
        task_uuid = task.get('uuid')
        if not self.__scheduler.get_job(task_uuid):
            logger.warning(f"任务uuid: {task_uuid}不存在")
            return False
        self.__scheduler.remove_job(task_uuid)
        self.__handle_start_task(
            uuid=task_uuid,
            exec_type=task.get('type'),
            shell=task.get('shell'),
            cwd=task.get("exec_path"),
            exec_time=task.get('time'),
            exec_week=task.get('week'),
            exec_count=task.get('count')
        )
        return True

    def __run_shell(self, script, uuid, cwd: str = None):
        """
        运行Shell脚本
        """
        if not cwd:
            cwd = os.path.join(os.getcwd(), "shell_run")
        if not os.path.exists(cwd):
            os.mkdir(cwd)
        logger.debug(f"run shell script")
        # 执行多行 shell 脚本，设置 shell=True 并使用 bash 解释器执行
        self.__process_list[uuid] = subprocess.Popen(
            ["bash", "-c", script],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        process_mark_uuid = str(uuid1())
        self.__process_mark[uuid] = process_mark_uuid
        self.__send_websocket_action('task:process_start', {
            'uuid': uuid,
            'mark': process_mark_uuid,
            'timestamp': time.time()
        })
        # 如果线程不存在则初始化线程
        if self.__get_process_thread is None:
            self.__get_process_thread = Thread(
                target=self.__get_process_output,
                args=()
            )
        # 如果线程未启动则启动线程
        if not self.__get_process_thread.is_alive():
            self.__get_process_thread.start()

    def __get_process_output(self):
        """获取所有进程输出"""
        while len(self.__process_list) > 0:
            for i in self.__process_list:
                process = self.__process_list[i]
                if process.poll():
                    self.__send_websocket_action("task:process_stop", {
                        'uuid': i,
                        'mark': self.__process_mark[i],
                        'code': process.returncode,
                        'timestamp': time.time()
                    })
                    del self.__process_list[i]
                    continue
                line = self.__process_list[i].stdout.readline()
                line = line.strip().decode('utf-8')
                if line:
                    logger.debug(f'[uuid: {i}]Subprogram output: {line}')
                    self.__send_websocket_action("task:process_output", {
                        'uuid': i,
                        'mark': self.__process_mark[i],
                        'line': line,
                        'timestamp': time.time()
                    })
            time.sleep(1)

    def __handle_start_task(self, uuid: str, exec_type: str, shell: str, cwd: str = None, exec_time: int = None,
                            exec_week: list[int] = None, exec_count: int = None) -> bool:
        """
        处理启动任务请求
        uuid: str 任务唯一标识符
        exec_type: str 执行类型
        shell: str 执行的命令
        cwd: str 执行器目录
        exec_time: int 运行时间
        exec_week: dict 运行周期(星期)
        exec_count: 运行次数
        """
        if not exec_type:
            logger.warning(f"任务uuid: {uuid}配置失败(缺少任务类型)")
            return False
        if not shell:
            logger.warning(f"任务uuid: {uuid}配置失败(缺少任务载荷)")
            return False
        match exec_type:
            case "date-time":
                # 指定时间任务
                self.__scheduler.add_job(
                    self.__run_shell,
                    args=[shell, uuid, cwd],
                    id=uuid,
                    name=uuid,
                    trigger='date',
                    run_date=datetime.fromtimestamp(exec_time)
                )
                return True
            case "cycle":
                # 周期任务
                if not exec_week:
                    logger.warning(f"任务uuid: {uuid}配置失败(缺少运行配置)")
                    return False
                logger.debug(self.__handle_week(exec_week))
                print(exec_time)
                hours = exec_time // 3600
                minutes = (exec_time % 3600) // 60
                logger.debug(f"hour: {hours} minute: {minutes}")
                print(uuid)
                if exec_count:
                    self.__scheduler.add_job(
                        self.__run_shell,
                        args=[shell, uuid, cwd],
                        id=uuid,
                        name=uuid,
                        trigger='cron',
                        day_of_week=self.__handle_week(exec_week),
                        hour=hours,
                        minute=minutes,
                        max_instances=exec_count
                    )
                    return True
                self.__scheduler.add_job(
                    self.__run_shell,
                    args=[shell, uuid, cwd],
                    id=uuid,
                    name=uuid,
                    trigger='cron',
                    day_of_week=self.__handle_week(exec_week),
                    hour=hours,
                    minute=minutes
                )
                return True
            case "interval":
                # 间隔任务
                logger.debug(exec_time)
                if exec_count:
                    self.__scheduler.add_job(
                        self.__run_shell,
                        args=[shell, uuid, cwd],
                        id=uuid,
                        name=uuid,
                        trigger='interval',
                        seconds=exec_time,
                        max_instances=exec_count
                    )
                    return True
                self.__scheduler.add_job(
                    self.__run_shell,
                    args=[shell, uuid, cwd],
                    id=uuid,
                    name=uuid,
                    trigger='interval',
                    seconds=exec_time,
                )
                return True
            case _:
                logger.error(f"未知的任务类型: {exec_type}")
                return False

    def __handle_week(self, week_list: list[int]) -> str:
        """
        处理星期
        """
        # 星期几的映射关系，1 表示星期一，7 表示星期天
        days_mapping = {
            1: 'mon',
            2: 'tue',
            3: 'wed',
            4: 'thu',
            5: 'fri',
            6: 'sat',
            7: 'sun'
        }

        # 将整数列表转换为逗号分隔的星期缩写字符串
        day_of_week = ','.join(days_mapping[day] for day in week_list)

        return day_of_week

    def __send_websocket_action(self, action, payload: dict = None):
        if payload is None:
            payload = {}
        def __send(data):
            asyncio.run(self.__websocket.websocket_send_json(data))
        Thread(target=__send, args=({
                'action': action,
                'data': payload
            },)).start()

