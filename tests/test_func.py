# def __handle_week(week_list: list[int]) -> str:
#     temp = ""
#     week_mappings = {
#         1: 'monday',
#         2: 'tuesday',
#         3: 'wednesday',
#         4: 'thursday',
#         5: 'friday',
#         6: 'saturday',
#         7: 'sunday',
#     }
#     for index, week in enumerate(week_list):
#
#         if index != len(week_list)-1:
#             temp += f"{week_mappings.get(week)},"
#             continue
#         temp += f"{week_mappings.get(week)}"
#     return temp

import time

if __name__ == '__main__':
    # print(__handle_week([]))
    print(time.time())