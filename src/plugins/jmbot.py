from nonebot import on_command
from nonebot.adapters.onebot.v11 import Message, MessageSegment, Bot, Event, GroupMessageEvent
from nonebot.params import CommandArg
import threading
import asyncio
import os
import jmcomic
from jmcomic import jm_entity
import img2pdf

import os

RES_PATH = os.path.abspath('E:/qqbot/QQ-Bot/src/tmp').replace('\\', '/')  # E:/qqbot/QQ-Bot/src/tmp
jm_option = jmcomic.create_option_by_file("E:/QQBOT/QQ-Bot/option.yml")
JM = on_command("jmcomic", aliases={"jm", "禁漫"}, priority=5, block=True)


@JM.handle()
async def handle_func(bot: Bot,  event: Event, msg: GroupMessageEvent, args: Message = CommandArg()) -> None:
    # dl_complete_flag = asyncio.Event()
    # __album_info = None
    queue = asyncio.Queue(maxsize=3)

    async def jm_send():
        # nonlocal __album_info
        jm_get_result = await queue.get()
        # await asyncio.wait_for(dl_complete_flag.wait(), timeout=120)
        if type(jm_get_result) == jm_entity.JmAlbumDetail:

            await bot.send(event=msg, message=Message("下载完成，正在尝试发送..."))
            img_paths = os.listdir(f"{RES_PATH}/{jm_get_result.album_id}")
        #["00001.jpg", "00002.jpg", "00003.jpg", ...]


            # 发送pdf
            output_pdf = f"{RES_PATH}/{jm_get_result.album_id}.pdf"
            # E:/qqbot/QQ-Bot/src/tmp/114514/114514.pdf
            img_pdf_paths = [f"{RES_PATH}/{jm_get_result.album_id}/{img_path}" for img_path in img_paths]
            print(img_pdf_paths)
            with open(output_pdf, "wb") as f:
                f.write(img2pdf.convert(img_pdf_paths))
            await bot.upload_group_file(group_id=msg.group_id, file=f"file:///{output_pdf}", name=f"{jm_get_result.album_id}.pdf")
            
            # 发送合并消息
            sent_count = 0
            node_list = []
            txt = MessageSegment.node_custom(user_id=959302031, nickname="AAA黄瓜批发睦姐", content=Message(MessageSegment.text(f'作者: [{jm_get_result.author}],\n'
                f'总页数: {jm_get_result.page_count},\n'
                f'标题: {jm_get_result.name},\n'
                f'关键词: {jm_get_result.tags}')))
            
            node_list.append(txt)
            for index, path in enumerate(img_paths):
                node = MessageSegment.node_custom(user_id=959302031, nickname="AAA黄瓜批发睦姐", content=Message(MessageSegment.image(file= f'file:///{RES_PATH}/{jm_get_result.album_id}/{path}', timeout=0xFFFFFFFF)))
                node_list.append(node)
                sent_count += 1
                if sent_count == 30:
                    try:# 每100张图发送一次
                        await bot.send_group_forward_msg(group_id=msg.group_id, messages=node_list)
                    except:
                        pass
                    node_list.clear()
                    sent_count = 0
                if index == len(img_paths) - 1:  # 结束时即使不够100张也发一次
                    if node_list:  # 排除整百的情况
                        try:
                            await bot.send_group_forward_msg(group_id=msg.group_id, messages=node_list)
                        except:
                            pass
                        return
        elif type(jm_get_result) == str:
            await bot.send(event=msg, message=Message(f"下载失败，错误信息：{jm_get_result}"))
    
    def jm_dl_cb(album: jm_entity.JmAlbumDetail, dldr):
        nonlocal queue
        # __album_info = album
        _ = queue.put(album)
        # dl_complete_flag.set()
    
    def jm_get(album_id: int):
        try:
            jmcomic.download_album(album_id, option=jm_option, callback=jm_dl_cb)
        except Exception as e:
            _ = queue.put(str(e))
            # print(e)
    
    if num := args.extract_plain_text():
        jm_thread = threading.Thread(target=jm_get, args=(num, ), daemon=False)
        jm_thread.start()
        await bot.send(event=msg, message=Message("正在下载中，请耐心等待..."))
        await jm_send()
        await JM.finish()
    else:
        await JM.finish("请发送正确的参数！")
