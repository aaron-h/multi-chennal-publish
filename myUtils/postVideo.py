import asyncio
from pathlib import Path

from conf import BASE_DIR
from uploader.douyin_uploader.main import DouYinVideo
from uploader.ks_uploader.main import KSVideo
from uploader.tencent_uploader.main import TencentVideo
from uploader.xiaohongshu_uploader.main import XiaoHongShuVideo
from utils.constant import TencentZoneTypes
from utils.files_times import generate_schedule_time_next_day


def _safe_report(reporter, **kwargs):
    if not reporter:
        return
    try:
        reporter(**kwargs)
    except Exception:
        # reporter should never break publishing
        return


def post_video_tencent(
    title,
    files,
    tags,
    account_file,
    category=TencentZoneTypes.LIFESTYLE.value,
    enableTimer=False,
    videos_per_day=1,
    daily_times=None,
    start_days=0,
    is_draft=False,
    reporter=None,
):
    # 生成文件的完整路径
    files_rel = list(files)
    accounts_rel = list(account_file)
    account_file = [Path(BASE_DIR / "cookiesFile" / file) for file in account_file]
    files = [Path(BASE_DIR / "videoFile" / file) for file in files]
    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(len(files), videos_per_day, daily_times,start_days)
    else:
        publish_datetimes = [0 for i in range(len(files))]
    for index, file in enumerate(files):
        for cookie in account_file:
            print(f"文件路径{str(file)}")
            # 打印视频文件名、标题和 hashtag
            print(f"视频文件名：{file}")
            print(f"标题：{title}")
            print(f"Hashtag：{tags}")
            app = TencentVideo(title, str(file), tags, publish_datetimes[index], cookie, category, is_draft)
            file_rel = files_rel[index]
            account_rel = cookie.name
            # try to map cookie back to rel path
            for a in accounts_rel:
                if str(a).endswith(cookie.name):
                    account_rel = a
                    break
            _safe_report(reporter, file_path=file_rel, account_file_path=account_rel, status="running", scheduled_at=publish_datetimes[index])
            try:
                asyncio.run(app.main(), debug=False)
                _safe_report(reporter, file_path=file_rel, account_file_path=account_rel, status="success", scheduled_at=publish_datetimes[index])
            except Exception as e:
                _safe_report(
                    reporter,
                    file_path=file_rel,
                    account_file_path=account_rel,
                    status="failed",
                    scheduled_at=publish_datetimes[index],
                    result_msg=str(e),
                )


def post_video_DouYin(
    title,
    files,
    tags,
    account_file,
    category=TencentZoneTypes.LIFESTYLE.value,
    enableTimer=False,
    videos_per_day=1,
    daily_times=None,
    start_days=0,
    thumbnail_path='',
    productLink='',
    productTitle='',
    reporter=None,
):
    # 生成文件的完整路径
    files_rel = list(files)
    accounts_rel = list(account_file)
    account_file = [Path(BASE_DIR / "cookiesFile" / file) for file in account_file]
    files = [Path(BASE_DIR / "videoFile" / file) for file in files]
    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(len(files), videos_per_day, daily_times,start_days)
    else:
        publish_datetimes = [0 for i in range(len(files))]
    for index, file in enumerate(files):
        for cookie in account_file:
            print(f"文件路径{str(file)}")
            # 打印视频文件名、标题和 hashtag
            print(f"视频文件名：{file}")
            print(f"标题：{title}")
            print(f"Hashtag：{tags}")
            app = DouYinVideo(title, str(file), tags, publish_datetimes[index], cookie, thumbnail_path, productLink, productTitle)
            file_rel = files_rel[index]
            account_rel = cookie.name
            for a in accounts_rel:
                if str(a).endswith(cookie.name):
                    account_rel = a
                    break
            _safe_report(reporter, file_path=file_rel, account_file_path=account_rel, status="running", scheduled_at=publish_datetimes[index])
            try:
                asyncio.run(app.main(), debug=False)
                _safe_report(reporter, file_path=file_rel, account_file_path=account_rel, status="success", scheduled_at=publish_datetimes[index])
            except Exception as e:
                _safe_report(
                    reporter,
                    file_path=file_rel,
                    account_file_path=account_rel,
                    status="failed",
                    scheduled_at=publish_datetimes[index],
                    result_msg=str(e),
                )


def post_video_ks(
    title,
    files,
    tags,
    account_file,
    category=TencentZoneTypes.LIFESTYLE.value,
    enableTimer=False,
    videos_per_day=1,
    daily_times=None,
    start_days=0,
    reporter=None,
):
    # 生成文件的完整路径
    files_rel = list(files)
    accounts_rel = list(account_file)
    account_file = [Path(BASE_DIR / "cookiesFile" / file) for file in account_file]
    files = [Path(BASE_DIR / "videoFile" / file) for file in files]
    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(len(files), videos_per_day, daily_times,start_days)
    else:
        publish_datetimes = [0 for i in range(len(files))]
    for index, file in enumerate(files):
        for cookie in account_file:
            print(f"文件路径{str(file)}")
            # 打印视频文件名、标题和 hashtag
            print(f"视频文件名：{file}")
            print(f"标题：{title}")
            print(f"Hashtag：{tags}")
            app = KSVideo(title, str(file), tags, publish_datetimes[index], cookie)
            file_rel = files_rel[index]
            account_rel = cookie.name
            for a in accounts_rel:
                if str(a).endswith(cookie.name):
                    account_rel = a
                    break
            _safe_report(reporter, file_path=file_rel, account_file_path=account_rel, status="running", scheduled_at=publish_datetimes[index])
            try:
                asyncio.run(app.main(), debug=False)
                _safe_report(reporter, file_path=file_rel, account_file_path=account_rel, status="success", scheduled_at=publish_datetimes[index])
            except Exception as e:
                _safe_report(
                    reporter,
                    file_path=file_rel,
                    account_file_path=account_rel,
                    status="failed",
                    scheduled_at=publish_datetimes[index],
                    result_msg=str(e),
                )

def post_video_xhs(
    title,
    files,
    tags,
    account_file,
    category=TencentZoneTypes.LIFESTYLE.value,
    enableTimer=False,
    videos_per_day=1,
    daily_times=None,
    start_days=0,
    reporter=None,
):
    # 生成文件的完整路径
    files_rel = list(files)
    accounts_rel = list(account_file)
    account_file = [Path(BASE_DIR / "cookiesFile" / file) for file in account_file]
    files = [Path(BASE_DIR / "videoFile" / file) for file in files]
    file_num = len(files)
    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(file_num, videos_per_day, daily_times,start_days)
    else:
        publish_datetimes = 0
    for index, file in enumerate(files):
        for cookie in account_file:
            # 打印视频文件名、标题和 hashtag
            print(f"视频文件名：{file}")
            print(f"标题：{title}")
            print(f"Hashtag：{tags}")
            app = XiaoHongShuVideo(title, file, tags, publish_datetimes, cookie)
            file_rel = files_rel[index]
            account_rel = cookie.name
            for a in accounts_rel:
                if str(a).endswith(cookie.name):
                    account_rel = a
                    break
            _safe_report(reporter, file_path=file_rel, account_file_path=account_rel, status="running", scheduled_at=publish_datetimes)
            try:
                asyncio.run(app.main(), debug=False)
                _safe_report(reporter, file_path=file_rel, account_file_path=account_rel, status="success", scheduled_at=publish_datetimes)
            except Exception as e:
                _safe_report(
                    reporter,
                    file_path=file_rel,
                    account_file_path=account_rel,
                    status="failed",
                    scheduled_at=publish_datetimes,
                    result_msg=str(e),
                )



# post_video("333",["demo.mp4"],"d","d")
# post_video_DouYin("333",["demo.mp4"],"d","d")