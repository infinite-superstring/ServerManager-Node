
class TaskRunData:
    start: str
    end: str
    code: int


class TaskItem:
    uuid: str  # 任务UUID
    type: str
    count: int  # 任务执行次数
    run_data: dict[str:TaskRunData]

