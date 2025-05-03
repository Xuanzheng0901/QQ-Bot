from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message, MessageSegment, Bot, Event, GroupMessageEvent
from nonebot.permission import SUPERUSER

import jmcomic
from jmcomic import jm_entity
import img2pdf

import os
import threading
import asyncio


#TODO: 解耦、移植适配:插件改为多文件结构,,,通过交互更改配置(节点、域名等)

RES_PATH = os.path.abspath('./plugins/nonebot_plugin_jmdldr/tmp').replace('\\', '/')  # E:/qqbot/QQ-Bot/src/tmp
jm_option = jmcomic.create_option_by_file(os.path.abspath('./plugins/nonebot_plugin_jmdldr/option.yml').replace('\\', '/') )
JM = on_command("jmcomic", aliases={"jm", "禁漫"}, priority=5, block=True)


@JM.handle()
async def handle_func(bot: Bot, event: Event, msg: GroupMessageEvent, args: Message = CommandArg()) -> None:
    queue = asyncio.Queue(maxsize=3)  # 同步函数与异步函数间通过消息队列通信
    usr_name = str(msg.sender.nickname)
    usr_id = int(msg.get_user_id())

    async def album_send(album: jm_entity.JmAlbumDetail):
        await bot.send(event=msg, message=Message(f"正在发送{album.album_id}..."))
        img_paths = os.listdir(f"{RES_PATH}/{album.album_id}")
        # ["00001.jpg", "00002.jpg", "00003.jpg", ...]

        # 发送pdf
        output_pdf = f"{RES_PATH}/{album.album_id}.pdf"
        # E:/qqbot/QQ-Bot/src/tmp/114514/114514.pdf
        img_pdf_paths = [f"{RES_PATH}/{album.album_id}/{img_path}" for img_path in img_paths]
        # print(img_pdf_paths)
        with open(output_pdf, "wb") as f:
            f.write(img2pdf.convert(img_pdf_paths))
        await bot.upload_group_file(group_id=msg.group_id, file=f"file:///{output_pdf}", name=f"{album.name}.pdf")

        # 发送合并消息
        sent_count = 0
        node_list = []
        txt = MessageSegment.node_custom(
            user_id=usr_id,
            nickname=usr_name,
            content=Message(MessageSegment.text(
                f'作者: {",".join(album.authors)},\n'
                f'总页数: {len(img_paths)},\n'
                f'标题: {album.name},\n'
                f'关键词: {",".join(album.tags)}\n'
                f'登场人物: {",".join(album.actors)}')))
        node_list.append(txt)
        first_msg = 1
        for index, path in enumerate(img_paths):
            node = MessageSegment.node_custom(
                user_id=usr_id,
                nickname=usr_name,
                content=Message(MessageSegment.image(
                    file= f'file:///{RES_PATH}/{album.album_id}/{path}',
                    timeout=0xFFFFFFFF)))
            node_list.append(node)
            sent_count += 1  # 避免0出现
            if sent_count % 30 == 0:  # 每30张图发送一次,一次上传太多图片会超时
                # TODO: 在合并消息头部添加页码标识 1-30, 31-60, 61-90...
                node_list.insert(first_msg, MessageSegment.node_custom(
                    user_id=usr_id,
                    nickname=usr_name,
                    content=Message(
                        MessageSegment.text(f"第{sent_count - 29}-{sent_count}页"))))
                first_msg = 0  # 在第一次插入时插入到本子信息之后
                try:
                    await bot.send_group_forward_msg(group_id=msg.group_id, messages=node_list)
                except:
                    pass
                node_list.clear()  # 清空列表
                # todo
            if index == len(img_paths) - 1:  # 结束时即使不够30张也发一次
                if node_list:  # 排除30倍数的情况。如果有30的倍数张,上面发完了会被清空,这里直接跳过
                    node_list.insert(0, MessageSegment.node_custom(user_id=usr_id, nickname=usr_name, content=Message(MessageSegment.text(f"第{sent_count - (sent_count % 30) + 1}-{sent_count}页"))))
                    try:
                        await bot.send_group_forward_msg(group_id=msg.group_id, messages=node_list)
                        # 发送合并消息
                    except:
                        pass
                    return

    def jm_dl_cb(album: jm_entity.JmAlbumDetail, dldr):  # 下载成功时的回调函数
        asyncio.run(queue.put(album))  # 向队列中铺铜album对象(本子信息)

    def jm_download(album_id: int):
        try:
            jmcomic.download_album(album_id, option=jm_option, callback=jm_dl_cb)
        except Exception as e:
            asyncio.run(queue.put(str(e)))  #下载出错时put str(错误信息)

    async def download_and_send():
        jm_thread = threading.Thread(target=jm_download, args=(num, ), daemon=False)
        jm_thread.start()  # 使用threading创建独立线程,避免长时间下载阻塞主进程
        await bot.send(event=msg, message=Message("下载中，请耐心等待..."))

        jm_get_result = await queue.get()  # 等待下载完成或出错时继续执行
        if type(jm_get_result) == jm_entity.JmAlbumDetail:
            await album_send(jm_get_result)  # 发送本子
        elif type(jm_get_result) == str:
            await bot.send(event=msg, message=Message(f"下载失败，错误信息：{jm_get_result}"))

    try:
        num = int(args.extract_plain_text())
    except:
        await JM.finish()

    if num:  # 获取消息中除了/jm之外的文本
        # TODO: 根据参数判断发送pdf或合并消息
        if os.path.exists(f"{RES_PATH}/{num}"):  # 如果本子已经下载过了
            client = jmcomic.JmOption.copy_option(jm_option).build_jm_client()
            album = client.get_album_detail(num)
            await album_send(album)  # 直接发送
        else:
            await download_and_send()  # 等待下载

        await JM.finish()
    else:
        await JM.finish("请发送正确的参数！")
        #TODO :响应式获取车牌


search_handle = on_command("jm搜索", aliases={"jmsearch"}, priority=4, block=True)

@search_handle.handle()
async def search(bot: Bot, event: Event, msg: GroupMessageEvent, args: Message = CommandArg()) -> None:
    queue = asyncio.Queue(maxsize=3)
    usr_name = str(msg.sender.nickname)
    usr_id = int(msg.get_user_id())

    def search_album(search_query: str):
        client = jmcomic.JmOption.copy_option(jm_option).build_jm_client()
        page : jmcomic.JmSearchPage = client.search_site(search_query=search_query, page=1)
        print(page)
        asyncio.run(queue.put(page))

    if order := args.extract_plain_text():
        threading.Thread(target=search_album, args=(order,), daemon=False).start()
        page: jmcomic.JmSearchPage = await queue.get()
        if page:
            result = []
            for album_id, title in page:
                result.append(f"[{album_id}]: [{title}]")
            text = "搜索结果:\n" + "\n".join(result)
            _ = MessageSegment.text(text)
            if len(text) > 200:
                __ = MessageSegment.node_custom(user_id=usr_id, nickname=usr_name, content=Message(_))
                await bot.send_group_forward_msg(group_id=msg.group_id, messages=[__])
            else:
                await search_handle.finish(_)
        else:
            await search_handle.finish("没有搜索到结果\n" \
                                        "搜尋的最佳姿勢？\n"
                                        "【包含搜尋】\n"
                                        "搜尋[+]全彩[空格][+]萝莉,僅顯示全彩且是萝莉的本本\n"
                                        "範例:+全彩 +萝莉\n\n"

                                        "【排除搜尋】\n"
                                        "搜尋全彩[空格][-]萝莉,顯示全彩並排除萝莉的本本\n"
                                        "範例:全彩 -萝莉\n\n"

                                        "【我都要搜尋】\n"
                                        "搜尋全彩[空格]萝莉,會顯示所有包含全彩及萝莉的本本\n"
                                        "範例:全彩 萝莉\n")
    else:
        await search_handle.finish("请发送正确的参数！")


tmp = on_command("jmtmp", priority=5, block=True, permission=SUPERUSER)

@tmp.handle()
async def get_temp_dir_size(bot: Bot, event: Event, msg: GroupMessageEvent, args: Message = CommandArg()):
    size = 0
    for root, dirs, files in os.walk(RES_PATH):
        size += sum([os.path.getsize(os.path.join(root, name)) for name in files])
    await tmp.finish(Message(MessageSegment.text(f"当前tmp目录大小为: {size / 1024 / 1024:.2f}MB")))
