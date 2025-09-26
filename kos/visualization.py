import matplotlib.pyplot as plt
import numpy as np
from matplotlib import rcParams

# 设置中文字体
rcParams['font.sans-serif'] = ['SimHei']  # 使用黑体
rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

# 10种颜色方案（每种方案10个颜色）
color_schemes = [
    # 方案1: 明亮彩虹色
    ['#FF0000', '#FF7F00', '#FFFF00', '#00FF00', '#00FFFF', 
     '#0000FF', '#4B0082', '#9400D3', '#FF1493', '#FF69B4'],
    
    # 方案2: 柔和马卡龙
    ['#FF9AA2', '#FFB7B2', '#FFDAC1', '#E2F0CB', '#B5EAD7',
     '#C7CEEA', '#F8B195', '#F67280', '#C06C84', '#6C5B7B'],
    
    # 方案3: 商务蓝调
    ['#003366', '#336699', '#6699CC', '#99CCFF', '#CCE5FF',
     '#2E5266', '#6E8898', '#9FB1BC', '#D3D0CB', '#E2C044'],
    
    # 方案4: 自然大地色
    ['#8B4513', '#A0522D', '#CD853F', '#D2B48C', '#F5DEB3',
     '#556B2F', '#6B8E23', '#BC8F8F', '#DAA520', '#B8860B'],
    
    # 方案5: 粉彩糖果
    ['#FFB6C1', '#FFD700', '#98FB98', '#87CEFA', '#DDA0DD',
     '#FFA07A', '#20B2AA', '#9370DB', '#FF6347', '#7B68EE'],
    
    # 方案6: 深色系
    ['#2F4F4F', '#556B2F', '#8B4513', '#483D8B', '#2E8B57',
     '#8B008B', '#9932CC', '#8B0000', '#FF8C00', '#8FBC8F'],
    
    # 方案7: 现代简约
    ['#E63946', '#F1FAEE', '#A8DADC', '#457B9D', '#1D3557',
     '#FFBE0B', '#FB5607', '#8338EC', '#3A86FF', '#FF006E'],
    
    # 方案8: 复古色调
    ['#6D214F', '#B33771', '#FF6B6B', '#FEA47F', '#F97F51',
     '#25CCF7', '#1B9CFC', '#EAB543', '#55E6C1', '#58B19F'],
    
    # 方案9: 冷色系
    ['#0A2463', '#3E92CC', '#D8315B', '#FFFAFF', '#1E1B18',
     '#7A93AC', '#92BCEA', '#AFB3F7', '#D5B0AC', '#F2D0A4'],
    
    # 方案10: 暖色系
    ['#FF5E5B', '#D8D8D8', '#FFFFEA', '#00CECB', '#FFED66',
     '#FDCB6E', '#E17055', '#6C5CE7', '#FD79A8', '#00B894']
]

def plot_bar_chart(labels, ydata, title, xlabel, ylabel, filename):
    """
    绘制柱状图
    """
    plt.figure(figsize=(12, 6))
    bars = plt.bar(labels, ydata, color='skyblue')
    plt.bar_label(bars, label_type='edge')  # 在柱子顶部显示数值

    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('%s_bar.png' % (filename))  # 保存为图片
    plt.show()

def plot_pie_chart(labels, sizes, title, filename):
    """
    绘制饼图
    """
    plt.figure(figsize=(8, 8))
    
    def make_autopct(values):
        def my_autopct(pct):
            total = sum(values)
            val = int(round(pct*total/100.0))
            return '{p:.1f}%\n({v:d})'.format(p=pct, v=val)
        return my_autopct

    plt.pie(sizes, 
        labels=labels, 
        autopct=make_autopct(sizes),  # 同时显示百分比和数值
        startangle=90,
        colors=color_schemes[1])

    plt.title(title)
    plt.tight_layout()
    plt.savefig('%s_pie.png' % (filename))  # 保存为图片
    plt.show()

# 评论热词数据
hot_words = ['鞋子', '链接', '好看', '求', '宝宝', '喜欢', '衣服', '裤子', '包包', '外套']
hot_counts = [157, 132, 98, 87, 76, 68, 65, 59, 53, 47]
plot_bar_chart(hot_words, hot_counts, '评论热词Top10统计', '热词', '出现次数', 'hot_words')

# 评论分类数据
categories = ['时尚穿搭', '产品购买', '情感互动', '问题反馈']
category_counts = [540, 420, 180, 60]
plot_pie_chart(categories, category_counts, '评论内容分类占比', 'comment_categories')

# 购买反馈关键词
feedback_words = ['舒服', '质量好', '质感', '百搭', '增高', '味道大', '硬邦邦']
feedback_counts = [32, 28, 25, 22, 15, 5, 3]
plot_bar_chart(feedback_words, feedback_counts, '购买反馈关键词统计', '热词', '出现次数', 'feedback_words')

# 舆情关键词
sentiment_words = ['爱了爱了', '超级喜欢', '绝了', '治愈', '期待', '失望', '不舒服']
sentiment_counts = [45, 38, 34, 28, 25, 7, 5]
plot_bar_chart(sentiment_words, sentiment_counts, '舆情关键词统计', '热词', '出现次数', 'sentiment_words')

# 共性问题
common_issues = ['链接找不到', '尺码咨询', '直播时间', '产品缺货', '价格疑问']
issue_counts = [89, 76, 65, 43, 32]
plot_bar_chart(common_issues, issue_counts, '共性问题统计', '热词', '出现次数', 'common_issues')

# 产品好评点
positive_points = ['舒适度', '设计感', '质量', '搭配效果', '推荐准确']
positive_counts = [78, 65, 58, 54, 47]
plot_bar_chart(positive_points, positive_counts, '产品好评点统计', '热词', '出现次数', 'positive_points')

# 产品差评点
negative_points = ['产品味道', '尺码不准', '材质问题', '价格高', '缺货']
negative_counts = [12, 9, 7, 6, 5]
plot_bar_chart(negative_points, negative_counts, '产品差评点统计', '热词', '出现次数', 'negative_points')

# 用户咨询问题
question_types = ['品牌/链接', '尺码建议', '搭配建议', '使用体验', '直播信息']
question_counts = [432, 187, 156, 143, 98]
plot_bar_chart(question_types, question_counts, '用户咨询问题统计', '问题类型', '出现次数', 'question_types')

# # 创建柱状图 - 评论热词统计
# plt.figure(figsize=(12, 6))
# plt.bar(hot_words, hot_counts, color='skyblue')
# plt.title('评论热词Top10统计')
# plt.xlabel('热词')
# plt.ylabel('出现次数')
# plt.xticks(rotation=45)
# plt.tight_layout()
# plt.savefig('hot_words_bar.png')  # 保存为图片
# plt.show()

# # 创建饼图 - 评论分类
# plt.figure(figsize=(8, 8))
# plt.pie(category_counts, 
#         labels=categories, 
#         autopct='%1.1f%%',
#         startangle=90,
#         colors=['#ff9999','#66b3ff','#99ff99','#ffcc99'])
# plt.title('评论内容分类占比')
# plt.tight_layout()
# plt.savefig('comment_categories_pie.png')  # 保存为图片
# plt.show()

# # 创建柱状图 - 购买反馈关键词统计
# plt.figure(figsize=(12, 6))
# plt.bar(feedback_words, feedback_counts, color='skyblue')
# plt.title('购买反馈关键词统计')
# plt.xlabel('热词')
# plt.ylabel('出现次数')
# plt.xticks(rotation=45)
# plt.tight_layout()
# plt.savefig('feedback_words_bar.png')  # 保存为图片
# plt.show()

# # 创建柱状图 - 舆情关键词统计
# plt.figure(figsize=(12, 6))
# plt.bar(sentiment_words, sentiment_counts, color='skyblue')
# plt.title('舆情关键词统计')
# plt.xlabel('热词')
# plt.ylabel('出现次数')
# plt.xticks(rotation=45)
# plt.tight_layout()
# plt.savefig('sentiment_words_bar.png')  # 保存为图片
# plt.show()

# # 创建柱状图 - 共性问题统计
# plt.figure(figsize=(12, 6))
# plt.bar(common_issues, issue_counts, color='skyblue')
# plt.title('共性问题统计')
# plt.xlabel('热词')
# plt.ylabel('出现次数')
# plt.xticks(rotation=45)
# plt.tight_layout()
# plt.savefig('common_issues_bar.png')  # 保存为图片
# plt.show()

# # 创建柱状图 - 产品好评点统计
# plt.figure(figsize=(12, 6))
# plt.bar(positive_points, positive_counts, color='skyblue')
# plt.title('产品好评点统计')
# plt.xlabel('热词')
# plt.ylabel('出现次数')
# plt.xticks(rotation=45)
# plt.tight_layout()
# plt.savefig('positive_points_bar.png')  # 保存为图片
# plt.show()

# # 创建柱状图 - 产品差评点统计
# plt.figure(figsize=(12, 6))
# plt.bar(negative_points, negative_counts, color='skyblue')
# plt.title('产品差评点统计')
# plt.xlabel('热词')
# plt.ylabel('出现次数')
# plt.xticks(rotation=45)
# plt.tight_layout()
# plt.savefig('negative_points_bar.png')  # 保存为图片
# plt.show()

# # 创建柱状图 - 用户咨询问题统计
# plt.figure(figsize=(12, 6))
# plt.bar(question_types, question_counts, color='skyblue')
# plt.title('用户咨询问题统计')
# plt.xlabel('热词')
# plt.ylabel('出现次数')
# plt.xticks(rotation=45)
# plt.tight_layout()
# plt.savefig('question_types_bar.png')  # 保存为图片
# plt.show()