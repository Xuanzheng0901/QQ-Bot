from fastapi.security import OAuth2PasswordRequestForm
from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message, MessageSegment, Bot, Event, GroupMessageEvent

import jmcomic
from jmcomic import jm_entity
import img2pdf

import os
import threading
import asyncio

RES_PATH = os.path.abspath('E:/qqbot/QQ-Bot/src/tmp').replace('\\', '/')  # E:/qqbot/QQ-Bot/src/tmp
jm_option = jmcomic.create_option_by_file("E:/QQBOT/QQ-Bot/option.yml")
JM = on_command("jmcomic", aliases={"jm", "禁漫"}, priority=5, block=True)


@JM.handle()
async def handle_func(bot: Bot, event: Event, msg: GroupMessageEvent, args: Message = CommandArg()) -> None:
    queue = asyncio.Queue(maxsize=3)  # 同步函数与异步函数间通过消息队列通信

    async def jm_send():
        jm_get_result = await queue.get()  # 下载完成或出错时继续执行
        if type(jm_get_result) == jm_entity.JmAlbumDetail:
            await bot.send(event=msg, message=Message("下载完成，正在尝试发送..."))

            img_paths = os.listdir(f"{RES_PATH}/{jm_get_result.album_id}")
            #["00001.jpg", "00002.jpg", "00003.jpg", ...]

            # 发送pdf
            output_pdf = f"{RES_PATH}/{jm_get_result.album_id}.pdf"
            # E:/qqbot/QQ-Bot/src/tmp/114514/114514.pdf
            img_pdf_paths = [f"{RES_PATH}/{jm_get_result.album_id}/{img_path}" for img_path in img_paths]
            # print(img_pdf_paths)
            with open(output_pdf, "wb") as f:
                f.write(img2pdf.convert(img_pdf_paths))
            await bot.upload_group_file(group_id=msg.group_id, file=f"file:///{output_pdf}", name=f"{jm_get_result.album_id}.pdf")
            
            # 发送合并消息
            sent_count = 0
            node_list = []
            txt = MessageSegment.node_custom(user_id=959302031, 
                                             nickname="AAA黄瓜批发睦姐", 
                                             content=Message(MessageSegment.text(
                                                f'作者: {jm_get_result.author},\n'
                                                f'总页数: {len(img_paths)},\n'
                                                f'标题: {jm_get_result.name},\n'
                                                f'关键词: {",".join(jm_get_result.tags)}')))
            
            node_list.append(txt)
            for index, path in enumerate(img_paths):
                node = MessageSegment.node_custom(user_id=959302031,
                                                  nickname="AAA黄瓜批发睦姐",
                                                  content=Message(MessageSegment.image(file= f'file:///{RES_PATH}/{jm_get_result.album_id}/{path}',
                                                                                       timeout=0xFFFFFFFF)))
                node_list.append(node)
                sent_count += 1  # 先+1再取余,避免0出现
                if sent_count % 30 == 0:  # 每30张图发送一次,一次上传太多图片会超时
                    # TODO: 在合并消息头部添加页码标识 1-30, 31-60, 61-90...
                    try: 
                        await bot.send_group_forward_msg(group_id=msg.group_id, messages=node_list)
                    except:
                        pass
                    node_list.clear()  # 清空列表
                    # todo
                if index == len(img_paths) - 1:  # 结束时即使不够30张也发一次
                    if node_list:  # 排除整百的情况
                        try:
                            await bot.send_group_forward_msg(group_id=msg.group_id, messages=node_list)
                            # 发送合并消息
                        except:
                            pass
                        return
        elif type(jm_get_result) == str:
            await bot.send(event=msg, message=Message(f"下载失败，错误信息：{jm_get_result}"))
    
    def jm_dl_cb(album: jm_entity.JmAlbumDetail, dldr):  # 下载成功时的回调函数
        asyncio.run(queue.put(album))  # 向队列中铺铜album对象(本子信息)

    def jm_get(album_id: int):
        try:
            jmcomic.download_album(album_id, option=jm_option, callback=jm_dl_cb)
        except Exception as e:
            asyncio.run(queue.put(str(e)))  #下载出错时put str(错误信息)

    if num := args.extract_plain_text():  # 获取消息中除了/jm之外的文本
        # TODO: 根据参数判断发送pdf或合并消息
        jm_thread = threading.Thread(target=jm_get, args=(num, ), daemon=False)
        jm_thread.start()  # 使用threading创建独立线程,避免长时间下载阻塞主进程
        await bot.send(event=msg, message=Message("正在下载中，请耐心等待..."))  
        await jm_send()  # 等待下载
        await JM.finish()
    else:
        await JM.finish("请发送正确的参数！")
        #TODO :响应式获取车牌


search_handle = on_command("jm搜索", aliases={"jmsearch"}, priority=4, block=True)

@search_handle.handle()
async def search(bot: Bot, event: Event, msg: GroupMessageEvent, args: Message = CommandArg()) -> None:
    queue = asyncio.Queue(maxsize=3)

    def search_album(search_query: str):
        client = jmcomic.JmOption.default().new_jm_client()
        page : jmcomic.JmSearchPage = client.search_site(search_query=search_query, page=1)
        asyncio.run(queue.put(page))

    if order := args.extract_plain_text():
        threading.Thread(target=search_album, args=(order,), daemon=False).start()
        page: jmcomic.JmSearchPage = await queue.get()
        if page:
            result = []
            for album_id, title in page:
                result.append(f"[{album_id}]: [{title}]")
            text = "搜索结果:\n" + "\n".join(result)
            await search_handle.finish(MessageSegment.text(text))
        else:
            await search_handle.finish("没有搜索到结果");