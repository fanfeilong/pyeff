import os
import shutil
import logging

def move(src, dst):
    '''
    优先使用 os.rename，如果涉及到跨文件系统，需要shutil.move
    '''
    try:
        os.rename(src, dst)
    except OSError as e:
        # 记录特定的错误信息
        logging.error(f"Renaming failed with error: {e}")

        try:
            shutil.move(src, dst)
        except Exception as e:  # 可以捕获更具体的异常，如shutil.Error
            # 如果shutil.move也失败，记录这次异常
            logging.error(f"Moving with shutil also failed: {e}")
            # 进一步处理异常，如重新抛出、用户通知或特定的错误恢复流程
            raise