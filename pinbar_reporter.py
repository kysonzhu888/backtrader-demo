import environment
import random

from datetime import timedelta

from database_helper import DatabaseHelper
from date_utils import DateUtils
from environment import group_chat_name_vip
import logging

from wechat_helper import WeChatHelper


class PinbarReporter:
    def __init__(self):
        self.db_helper = DatabaseHelper()

    def report_recent_pinbars(self):
        # 获取当前时间
        current_time = DateUtils.now()
        # 查询2分钟内且未播报的数据
        recent_pinbars = self.db_helper.get_recent_unbroadcasted_pinbars(current_time, timedelta(minutes=2))
        # 查询2分钟内已播报过的数据
        broadcasted_pinbars = self.db_helper.get_recent_broadcasted_pinbars(current_time, timedelta(minutes=2))
        recent_pinbars = self._filter_and_mark_broadcasted(recent_pinbars, broadcasted_pinbars)

        # 按 product_type 分组
        pinbar_dict = {}
        for pinbar_item in recent_pinbars:
            product_type = pinbar_item.product_type
            if product_type not in pinbar_dict:
                pinbar_dict[product_type] = []
            pinbar_dict[product_type].append(pinbar_item)

        # 判断 pinbar_dict 中的项目数量
        if len(pinbar_dict) >= 4:
            high_score_msgs = []
            low_score_msgs = []
            for product_type, pinbars in pinbar_dict.items():
                for pinbar in pinbars:
                    if pinbar.score > 5:
                        high_score_msgs.append(
                            f"{pinbar.product_name}({pinbar.product_type}) 在多个周期下形成了信号共振，其中，{pinbar.interval} 下成功率 {pinbar.score * 15}%")
                    elif pinbar.score > 4:
                        low_score_msgs.append(
                            f"{pinbar.product_name}({pinbar.product_type}) ，{pinbar.interval} 周期出现信号，成功率 {pinbar.score * 15}%")
                    else:
                        logging.info(f"{pinbar.product_name}({pinbar.product_type}) ，{pinbar.interval} 周期出现信号，成功率 {pinbar.score * 15}%")

            # 记录已播报的商品
            reported_products = set()

            # 去除 high_score_msgs 中的重复消息
            unique_high_score_msgs = list(set(high_score_msgs))

            # 播报高分 pinbar
            for msg in unique_high_score_msgs:
                wx_helper = WeChatHelper()
                wx_helper.send_message(msg, group_chat_name_vip)
                # 记录已播报的商品
                product_name = msg.split(' ')[0]
                reported_products.add(product_name)

            # 合并低分 pinbar，排除已播报的商品
            if low_score_msgs:
                filtered_low_score_msgs = []
                for msg in low_score_msgs:
                    product_name = msg.split('，')[0]
                    if product_name not in reported_products:
                        filtered_low_score_msgs.append(msg)
                        reported_products.add(product_name)

                if filtered_low_score_msgs:
                    if len(high_score_msgs) > 0:
                        combined_msg = "低分开单信号有：\n" + "；\n".join(filtered_low_score_msgs)
                    else:
                        combined_msg = "其他开单信号还有：\n" + "；\n".join(filtered_low_score_msgs)

                    wx_helper = WeChatHelper()
                    wx_helper.send_message(combined_msg, group_chat_name_vip)
        else:
            for product_type, pinbars in pinbar_dict.items():
                if len(pinbars) > 1:
                    # 合并多个周期下的 pinbar
                    max_score_pinbar = max(pinbars, key=lambda x: x.score)
                    product_name = max_score_pinbar.product_name
                    score = max_score_pinbar.score
                    product_type = max_score_pinbar.product_type
                    msg = f"{product_name}({product_type}) 在多个周期下形成了信号共振，其中，{max_score_pinbar.interval} 下成功率 {score * 15}%"
                    if score > 4:
                        wx_helper = WeChatHelper()
                        wx_helper.send_message(msg, group_chat_name_vip)
                else:
                    pinbar = pinbars[0]
                    score = pinbar.score
                    score_detail_str = pinbar.score_detail
                    product_name = pinbar.product_name
                    product_type = pinbar.product_type
                    interval = pinbar.interval
                    key_level_strength = pinbar.key_level_strength

                    # 构建消息
                    msg = self.construct_message(score=score, product_type=product_type, product_name=product_name,
                                                 interval=interval)

                    # 发送消息
                    if score > 4:
                        wx_helper = WeChatHelper()
                        wx_helper.send_message(msg, group_chat_name_vip)
                    else:
                        logging.info(f"Score less than 4 for {product_name}, message not sent.")
        # 简单粗暴：遍历2分钟内的所有pinbar，全部置为已播报
        for pinbar in recent_pinbars:
            self.db_helper.set_pinbar_broadcasted(pinbar.id)

    def _filter_and_mark_broadcasted(self, recent_pinbars, broadcasted_pinbars):
        """
        根据四元组去重，并对重复项直接置 broadcast 为 True，返回未重复的 pinbar 列表
        """
        broadcasted_keys = set((p.product_type, p.interval, p.score, p.key_level_strength) for p in broadcasted_pinbars)
        filtered_pinbars = []
        for p in recent_pinbars:
            key = (p.product_type, p.interval, p.score, p.key_level_strength)
            if key in broadcasted_keys:
                self.db_helper.set_pinbar_broadcasted(p.id)
            else:
                filtered_pinbars.append(p)
        return filtered_pinbars

    @staticmethod
    def construct_message(score, product_type, product_name, interval):
        if score == 6:
            order_statement = ["干就完了","该下单了，兄弟","卖房！梭哈","机会永远只留给有准备的人"]
            random_choice = random.choice(order_statement)
            return f"请注意，{product_name}({product_type}) {interval} 的入场信号来了！成功率 {score * 15}% ，{random_choice}！"
        elif score == 5:
            order_statement = ["人生难得几回搏，此时不博待何时","搏一搏，单车变摩托","千年等一回，终于等到下单的机会了"]
            random_choice = random.choice(order_statement)
            return f"请注意，{product_name}({product_type}) {interval} 的入场信号来了！成功率 {score * 15}% ，{random_choice}！"
        elif score == 4:
            or_st = ["激动的心，颤抖的手","艺高人胆大","小仓位试错一下也许可以"]
            rn_ch = random.choice(or_st)
            return f"请注意，{product_name}({product_type}) {interval} 的开单信号来了！成功率 {score * 15}% ，{rn_ch}"
        elif score <= 3:
            or_st = [ "稳住，我们能赢", "投资有风险，开单需谨慎", "投资需要的是等待","虽然可能会赚，但我劝你忍住"]
            rn_ch = random.choice(or_st)
            return f"请注意，{product_name}({product_type}) {interval} 的开单信号来了！成功率 {score * 15}% ，{rn_ch}"


if __name__ == "__main__":
    reporter = PinbarReporter()
    reporter.report_recent_pinbars()
