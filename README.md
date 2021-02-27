Light Async Spider
===
Good Coder Exam Topic : mini\_spider

Asynchronous Mini Spider with native asynchronous I/O HTTPS, and webkit support defining and implementing Remote Inject js Call \(RIJC\)  wireless protocol

轻量爬虫

全异步轻量级爬虫, 原生支持Multiplexing和异步I/O，支持HTTPS, WebKit技术(定义和实现了"远程注入js调用"无线协议)

异步框架python版本改编思路来自于 Guido van Rossum 在不早于2015年的社区文章[A Web Crawler With Asyncio Crotoutines](https://www.aosabook.org/en/500L/a-web-crawler-with-asyncio-coroutines.html#fn2), 并重点支持了webkit, https, 以及 socket 异步io回调技术改进。改进后的组件，可以水平无限扩展（任意I/O时间，包括不限socket, pipe, 磁盘文件），在不考虑单线程流量限制的情况下，最大限度利用了单线程的I/O性能。

项目背景
---

早在15年笔者在做机器学习实验时，需要积累数据，遍开始实施相关爬虫技术。当时开源爬虫框架Scrapy采用twist promise/reactor模式来进行代码组织，笔者因为需要对Facebook, Taobao 进行爬去，考虑到Scapy并不支持Webkit解析，便贡献了如下组件：

> https://github.com/scrapy/scrapy/pull/1326

用以支持Webkit环境下js运行和解析。作为该技术的副产品，通过以下三个核心技术手段对SNS的反收录进行了突破，并成功突破相防御，获得大量原始数据积累

1. Tor + proxy: 区别于传统Throttling策略，我决定转向依靠真实模拟用户请求，并在匿名回环网络里，进行溯源欺骗，彻底杜绝范风控在2015年制定的反收录策略
2. 增加基于v8引擎的webkit解析环境，并在2015年大获成功

Scapy采用 twist 框架，随后大大降低了代码更新进度，而始终不得迁移到python3; 同时异步I/O技术更加成熟。为了避免回调地狱，人们开始引入CPU执行流水跳转技术，从而顺序执行异步代码，并进行语言层面的整合。这一点在2013发布的V8引擎上的node以及核心基础库libevent完成。这意味这Scrapy赖以存的Twist技术，逐渐失去根基，项目面临死亡（2015年下半年，我们发现Scrapy项目更新缓慢，且与主流技术脱轨）。

通过汇编层面寄存寻址编码，完成高效切换CPU运行开始普及到异步I/O Multiplexing技术，随后在系统库boost, libco等通过内联汇编完成相关实现，在系统层面打下坚实基础。实现诀窍在于堆分配的函数栈空间上，加入保存当前基寄存器地址，复原堆上函数栈对象调用地址，并进行想内核发送跳转指令。


Guido 在 2013年 node发布同年，在PyCon 2013已经引入asyncio库, 并于次年Python3.4版本正式发布。由于爬虫是程序是一个经典的I/O bounded场景，Guido 在不早于2015年撰写并发布了技术文章，详细阐述了 asyncio 设计思路。

Guido设计了yield语义，用来完成上述汇编的地址寻址功能，而且同时整个python函数栈都是在堆上，这样做很方便。利用这个语义，我们很快就可以设计出一个等效的执行流水切换代码，只是流程需要有一个主调用来驱动，我继承了这个思想进行I/O扩展，并形成了该轻量级库，用于定向内容收录。

由于作者工作需要，阅读了并熟悉了主流网络代码库源代码, 像手术刀一样的切开http/https协议访问下web处理规则，和中间流程，因此代码十分精简。

快速开始
---
代码在python3.5+下测试通过，理论上只依赖yield语义。

安装依赖：

> pip3 -r requirements.txt

安装node工具包：

> sh scripts/install.sh

如果访问速度较慢，请阅读requirements.txt添加国内镜像地址

修改配置文件 config/settings.py :

1. TSL证书地址
2. HTTPS加密方法

如需要配置代理，和 UserAgent等中间件，请参考其他成熟的项目，参考 core/downloader/handlers/ 中 Rquest 的写法，并按照 HTTP 报文要求，和代理服务器API规则修改 报文 和 socket 发送地址和参数。

测试
---
本测试用例部用于涉及I/O 和 框架， 只提供关键函数的访问测试，可用于严重异步 I/O 请求功能。

> python3 test/core/downloader/handlers/test_async_socket_http11.py

如何贡献
---
RoadMap:

路径：

1. 解耦目前base spider 和 donwloader的写法，以支持更多不同的下载策略
2. 建立内容收录图节点和相关超链路径分析
3. 建立缓存层
5. 增加多进程和线程在异步IO模式下的支持，充分利用系统硬件资源，把CPU负载I/O，带宽，再提升一个水平

项目设计
---
```txt
设计简要说明：

1. 设计目标：
1.1 验证技术思路：将aysnc io整合进入爬虫io流水线，使得顺序执行异步操作，每当有新的io事件，完成，即跳转到需要继续执行的代码跨，继续执行。
1.2 能够处理基本http/https的处理状态，不求全求大， 能够完成1.3目标任务
1.3 完成基本的爬虫功能，可以定向抓取内容，并通过xpath等规则进行超链分析

2. 总体设计：
根据我们的设计目标，我们将核心技术和业务代码拆开；

核心技术，由 downloader 下载器，base_spider 基础爬虫算法 组合能够。downloader里完成1.1抽象设计，处理从url访问，到内容获取这部分数据处理

业务代码，在根目录的mini_spider里实现期基础逻辑，每次爬虫返回的信息，将被解析成dom tree对象，该数据对象，可根据定义的规则进行超链拉取，超链存贮，以及配置媒体资源下载。

一般情况下，我们会配置数据服务层，比如设计一个数据库接口，和一个缓存接口。由于本题目只是将读取的html数据资源到磁盘上，就没有提供了。

进一步，本案例提供了超媒体中特定媒体资源，例如图像资源的异步下载功能，并保存在磁盘项目图像目录里。

3. 详细设计
详细设计背景，见README.md背景部分。由于本项目为了突出设计目标1.1，未混合异步I/O和多线程技术资源，一定程度上网络带宽海还有提高空间，单在单线程利用上，以及达到python可以完成的最佳水准。首先，核心模块输入是所有的 i/o 事件，如  http访问请求，文件下载等操作，需要重新编写，因为我们需要显示地控制异步I/O流程。输出是http报文解析，注意这里不是我们的重点，我们可以通过mock数据，利用已有的代码完成解析。

为了描述算法，我们先描述几个概念。

3.1 回调抽象
所有的io事件回调抽象为一个Future对象，并通过其记录返回地址。这里特殊地使用了python yield语义来实现设计目标。

3.2 I/O轮询
主函数不会阻塞，依次执行CPU流水，直到遇到I/O事件，利用yield发起中断，返回到主轮询模块。这样我们就实现回到I/O轮询上，始终让可以决定CPU跳转到哪里去执行代码，不空闲。我们把事件分为读，和写两种，读就是发起请求；写就是处理请求。

3.2.1 从轮询到函数处理现场
我们需要确保I/O处理完毕后，系统继续跳转到需要被执行的代码块，分两种情况：
（1）对于读事件，系统需要跳转到，文件可读的代码部分（比如一次socket.send后，需要读取文件）

（2）对于写事件，系统需要跳转，文件代码可写部分（比如一次socket.connect 后，需要写请求发送出去）

对于1，2，只需要了解在python语义下怎么完成即可，具体地是通过generator 的send语义完成，send(ret) 完成跳转的同时，会把ret带入到现场，从而将I/O结果带过去。

这里执行周期从Future回调函数send一次，就会继续返回Task执行层；这里我在Task函数做了路径压缩，严格意义上将，可以看出和python作者理解不同，我的任务只返回I/O引起的中断，因此在执行到event_loop时，只需等待I/O唤醒，并跳转回Task位置继续执行。

3.3.2 从函数处理现场到轮询：
实际上调用栈顶，仍然是轮询，最简单的情况下只有一个I/O操作，处理完后，即从Process_Reader/Writer 返回到主轮询；复杂情况下，会在Process_Reader/Writer里面进行嵌套。所有相关函数栈因有指引，不会立即释放。理论上，函数栈不宜过身。否则会有大量内存被占用。


3.3 总结

有了上述概念和方法论后，我们就可以进行具体地编码.


3.3.1 core/downloader

downloader剩下I/O策略，处理http/https请求，重定向，媒体文件访问等。

特别地我们实现了异步I/O下的http/https文件访问读取策略。并提供了webkit_runtime_downloader作为扩展，证明精简框架中的代码可扩展性。

其主要逻辑为：主现场执行 I/O 轮询，并通过callback发起中断，跳转到代码执行区。该过程会在回调函数内部嵌套，以实现多类型I/O的整合，并最终完成多路I/O单线程并行技术。


3.3.2 core/spider

用于实现爬虫收录算法基类。用户可自行编写数据层，和可持久化层。所有抓群文件会被解析为dom对象，供用户进一步分析。

3.3.3 mini_spider

业务逻辑入口，屏蔽了算法层面和网络层面的问题，让用户专注于超链分析本身。
```

版本信息
---
V1.0 增加`mini_spider`项目

维护者
---
### owners
* yiakwy (yiak.wy@gmail.com)

### committers
* yiakwy (yiak.wy@gmail.com)

