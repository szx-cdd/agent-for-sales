from fastapi import FastAPI, Request, Form, UploadFile, File, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openai import OpenAI
import json
import re
from typing import List, Optional
from config import settings
from prompts import (
    CUSTOMER_PROFILE_PROMPT,
    FOLLOWUP_PLAN_PROMPT,
    OBJECTION_HANDLING_PROMPT,
    SILENT_REACTIVATION_PROMPT,
    FULL_ANALYSIS_PROMPT
)
from document_processor import doc_processor
from database import db

app = FastAPI(title="销售成单推演 Agent")

# 静态文件和模板
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except:
    pass
templates = Jinja2Templates(directory="templates")

# Kimi (Moonshot) 客户端
client = OpenAI(
    api_key=settings.kimi_api_key,
    base_url=settings.kimi_base_url
)


def call_kimi(prompt: str) -> dict:
    """调用 Kimi API"""
    try:
        response = client.chat.completions.create(
            model=settings.kimi_text_model,
            max_tokens=settings.max_tokens,
            temperature=settings.temperature,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        content = response.choices[0].message.content

        # 尝试提取 JSON
        try:
            # 查找 JSON 块
            json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))

            # 尝试直接解析
            return json.loads(content)
        except:
            # 返回原始文本包装
            return {"raw_response": content}

    except Exception as e:
        return {"error": str(e)}


# ========== 页面路由 ==========

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """主页 - 销售推演表单"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/customers", response_class=HTMLResponse)
async def customers_page(request: Request):
    """客户管理页面"""
    return templates.TemplateResponse("customers.html", {"request": request})


@app.get("/customers/{customer_id}", response_class=HTMLResponse)
async def customer_detail_page(request: Request, customer_id: int):
    """客户详情页面"""
    customer = db.get_customer(customer_id)
    if not customer:
        return RedirectResponse(url="/customers")
    return templates.TemplateResponse("customer_detail.html", {
        "request": request,
        "customer": customer
    })


# ========== 客户管理 API ==========

@app.post("/api/customers")
async def create_customer(
    name: str = Form(...),
    company: str = Form(None),
    industry: str = Form(None),
    phone: str = Form(None),
    email: str = Form(None),
    notes: str = Form(None)
):
    """创建新客户"""
    try:
        customer_id = db.create_customer(
            name=name,
            company=company,
            industry=industry,
            phone=phone,
            email=email,
            notes=notes
        )
        return JSONResponse({
            "success": True,
            "customer_id": customer_id,
            "message": "客户创建成功"
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/customers")
async def get_customers(
    search: str = Query(None),
    industry: str = Query(None)
):
    """获取客户列表"""
    try:
        customers = db.get_customers(search=search, industry=industry)
        return JSONResponse({
            "success": True,
            "customers": customers
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/customers/{customer_id}")
async def get_customer(customer_id: int):
    """获取客户详情"""
    try:
        customer = db.get_customer(customer_id)
        if not customer:
            return JSONResponse({
                "success": False,
                "error": "客户不存在"
            }, status_code=404)

        # 获取最新画像
        latest_profile = db.get_latest_profile(customer_id)

        # 获取分析历史数量
        analysis_histories = db.get_analysis_histories(customer_id)

        # 获取聊天记录数量
        chat_histories = db.get_chat_histories(customer_id)

        return JSONResponse({
            "success": True,
            "customer": customer,
            "latest_profile": latest_profile,
            "analysis_count": len(analysis_histories),
            "chat_count": len(chat_histories)
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.put("/api/customers/{customer_id}")
async def update_customer(
    customer_id: int,
    name: str = Form(None),
    company: str = Form(None),
    industry: str = Form(None),
    phone: str = Form(None),
    email: str = Form(None),
    notes: str = Form(None)
):
    """更新客户信息"""
    try:
        success = db.update_customer(
            customer_id,
            name=name,
            company=company,
            industry=industry,
            phone=phone,
            email=email,
            notes=notes
        )
        if success:
            return JSONResponse({
                "success": True,
                "message": "客户信息更新成功"
            })
        else:
            return JSONResponse({
                "success": False,
                "error": "客户不存在或无需更新"
            }, status_code=404)
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.delete("/api/customers/{customer_id}")
async def delete_customer(customer_id: int):
    """删除客户"""
    try:
        success = db.delete_customer(customer_id)
        if success:
            return JSONResponse({
                "success": True,
                "message": "客户删除成功"
            })
        else:
            return JSONResponse({
                "success": False,
                "error": "客户不存在"
            }, status_code=404)
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


# ========== 聊天记录管理 API ==========

@app.post("/api/customers/{customer_id}/chat")
async def add_chat_history(
    customer_id: int,
    content: str = Form(...),
    source_type: str = Form("manual"),
    files: List[UploadFile] = File(None)
):
    """添加客户聊天记录"""
    try:
        # 检查客户是否存在
        customer = db.get_customer(customer_id)
        if not customer:
            return JSONResponse({
                "success": False,
                "error": "客户不存在"
            }, status_code=404)

        all_content = []
        processed_files = []

        # 处理上传的文件
        if files:
            for file in files:
                file_content = await file.read()
                result = doc_processor.process_file(file_content, file.filename)

                if result['type'] != 'unsupported':
                    all_content.append(f"=== {file.filename} ===\n{result['content']}")
                    processed_files.append({
                        "filename": file.filename,
                        "type": result['type'],
                        "content": result['content']
                    })

        # 添加手动输入的内容
        if content.strip():
            all_content.append(content.strip())

        if not all_content:
            return JSONResponse({
                "success": False,
                "error": "没有提供聊天记录内容"
            }, status_code=400)

        # 保存到数据库
        final_content = "\n\n".join(all_content)
        chat_id = db.add_chat_history(
            customer_id=customer_id,
            content=final_content,
            source_type=source_type if not files else "file_upload",
            source_file=", ".join([f['filename'] for f in processed_files]) if processed_files else None
        )

        return JSONResponse({
            "success": True,
            "chat_id": chat_id,
            "message": "聊天记录添加成功",
            "processed_files": processed_files
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/customers/{customer_id}/chat")
async def get_chat_histories(customer_id: int, limit: int = Query(50)):
    """获取客户聊天记录"""
    try:
        histories = db.get_chat_histories(customer_id, limit=limit)
        return JSONResponse({
            "success": True,
            "histories": histories
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


# ========== 分析历史 API ==========

@app.get("/api/customers/{customer_id}/analysis")
async def get_analysis_histories(
    customer_id: int,
    analysis_type: str = Query(None)
):
    """获取客户分析历史"""
    try:
        histories = db.get_analysis_histories(customer_id, analysis_type)
        return JSONResponse({
            "success": True,
            "histories": histories
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/customers/{customer_id}/analyze")
async def analyze_customer_with_history(
    customer_id: int,
    analysis_type: str = Form("full"),
    new_chat: str = Form(None),
    include_history: bool = Form(True)
):
    """
    基于历史记录+新记录分析客户
    如果include_history为True，会合并历史聊天记录进行分析
    """
    try:
        # 检查客户是否存在
        customer = db.get_customer(customer_id)
        if not customer:
            return JSONResponse({
                "success": False,
                "error": "客户不存在"
            }, status_code=404)

        # 获取历史聊天记录
        history_chat = ""
        if include_history:
            history_chat = db.get_all_chat_content(customer_id)

        # 合并新记录
        final_chat = history_chat
        if new_chat and new_chat.strip():
            if final_chat:
                final_chat += "\n\n=== 最新记录 ===\n" + new_chat.strip()
            else:
                final_chat = new_chat.strip()

        # 如果没有聊天记录，使用客户的notes作为基础信息
        customer_info = customer.get('notes', '') or ''
        if not final_chat and not customer_info:
            return JSONResponse({
                "success": False,
                "error": "没有足够的客户信息进行分析，请先添加聊天记录或客户备注"
            }, status_code=400)

        # 获取之前的分析结果作为参考
        previous_profile = db.get_latest_profile(customer_id)

        # 构建Prompt
        if analysis_type == "profile":
            prompt = CUSTOMER_PROFILE_PROMPT.format(
                industry=customer.get('industry', '未知'),
                customer_info=customer_info,
                chat_history=final_chat or "暂无详细聊天记录"
            )
        elif analysis_type == "full":
            # 如果已有历史画像，在Prompt中提及
            if previous_profile:
                profile_context = f"\n\n之前对该客户的画像分析：\n{json.dumps(previous_profile.get('profile_data', {}), ensure_ascii=False)}"
                prompt = FULL_ANALYSIS_PROMPT.format(
                    industry=customer.get('industry', '未知'),
                    customer_info=customer_info + profile_context,
                    chat_history=final_chat or "暂无详细聊天记录"
                )
            else:
                prompt = FULL_ANALYSIS_PROMPT.format(
                    industry=customer.get('industry', '未知'),
                    customer_info=customer_info,
                    chat_history=final_chat or "暂无详细聊天记录"
                )
        elif analysis_type == "followup":
            # 获取最新的客户画像
            if not previous_profile:
                # 先生成画像
                profile_prompt = CUSTOMER_PROFILE_PROMPT.format(
                    industry=customer.get('industry', '未知'),
                    customer_info=customer_info,
                    chat_history=final_chat or "暂无详细聊天记录"
                )
                previous_profile = {'profile_data': call_kimi(profile_prompt)}

            prompt = FOLLOWUP_PLAN_PROMPT.format(
                customer_profile=json.dumps(previous_profile.get('profile_data', {}), ensure_ascii=False),
                chat_history=final_chat or "暂无详细聊天记录"
            )
        elif analysis_type == "objection":
            if not previous_profile:
                profile_prompt = CUSTOMER_PROFILE_PROMPT.format(
                    industry=customer.get('industry', '未知'),
                    customer_info=customer_info,
                    chat_history=final_chat or "暂无详细聊天记录"
                )
                previous_profile = {'profile_data': call_kimi(profile_prompt)}

            prompt = OBJECTION_HANDLING_PROMPT.format(
                customer_profile=json.dumps(previous_profile.get('profile_data', {}), ensure_ascii=False),
                latest_reply=new_chat.split("\n")[-1] if new_chat else (final_chat.split("\n")[-1] if final_chat else "暂无")
            )
        else:
            return JSONResponse({
                "success": False,
                "error": "未知的分析类型"
            }, status_code=400)

        # 调用AI分析
        result = call_kimi(prompt)

        # 保存分析结果
        db.save_analysis(
            customer_id=customer_id,
            analysis_type=analysis_type,
            result=result,
            chat_summary=final_chat[:500] if final_chat else None
        )

        # 如果是画像分析，也保存到画像表
        if analysis_type == "profile" and "性格类型" in result:
            db.save_profile(customer_id, result)

        return JSONResponse({
            "success": True,
            "result": result,
            "message": "分析完成并已保存"
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


# ========== 统计 API ==========

@app.get("/api/statistics")
async def get_statistics():
    """获取统计数据"""
    try:
        stats = db.get_statistics()
        return JSONResponse({
            "success": True,
            "statistics": stats
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


# ========== 原有的分析 API（保留向后兼容） ==========

@app.post("/api/analyze")
async def analyze_customer(
    industry: str = Form(...),
    customer_info: str = Form(...),
    chat_history: str = Form(""),
    analysis_type: str = Form("full")
):
    """分析客户并返回成单推演方案（无需客户管理）"""

    if analysis_type == "profile":
        prompt = CUSTOMER_PROFILE_PROMPT.format(
            industry=industry,
            customer_info=customer_info,
            chat_history=chat_history or "暂无聊天记录"
        )
    elif analysis_type == "full":
        prompt = FULL_ANALYSIS_PROMPT.format(
            industry=industry,
            customer_info=customer_info,
            chat_history=chat_history or "暂无聊天记录"
        )
    else:
        # 先获取客户画像作为基础
        profile_prompt = CUSTOMER_PROFILE_PROMPT.format(
            industry=industry,
            customer_info=customer_info,
            chat_history=chat_history or "暂无聊天记录"
        )
        profile_result = call_kimi(profile_prompt)

        if analysis_type == "followup":
            prompt = FOLLOWUP_PLAN_PROMPT.format(
                customer_profile=json.dumps(profile_result, ensure_ascii=False),
                chat_history=chat_history or "暂无聊天记录"
            )
        elif analysis_type == "objection":
            prompt = OBJECTION_HANDLING_PROMPT.format(
                customer_profile=json.dumps(profile_result, ensure_ascii=False),
                latest_reply=chat_history.split("\n")[-1] if chat_history else "暂无"
            )
        else:
            return JSONResponse({"error": "未知的分析类型"}, status_code=400)

    result = call_kimi(prompt)
    return JSONResponse(result)


@app.post("/api/reactivate")
async def reactivate_silent(
    industry: str = Form(...),
    silent_days: int = Form(...),
    last_conversation: str = Form(...),
    interaction_history: str = Form("")
):
    """沉默客户激活方案"""

    prompt = SILENT_REACTIVATION_PROMPT.format(
        industry=industry,
        silent_days=silent_days,
        last_conversation=last_conversation,
        interaction_history=interaction_history or "无"
    )

    result = call_kimi(prompt)
    return JSONResponse(result)


@app.post("/api/upload-files")
async def upload_files(
    files: List[UploadFile] = File(...)
):
    """上传并处理文件"""
    try:
        processed_files = []

        for file in files:
            content = await file.read()
            result = doc_processor.process_file(content, file.filename)
            processed_files.append(result)

        # 合并所有提取的文本
        all_text = []
        for result in processed_files:
            if result['type'] == 'unsupported':
                all_text.append(f"【{result['filename']}】: {result['content']}")
            else:
                all_text.append(f"=== {result['filename']} ===\n{result['content']}")

        return JSONResponse({
            "success": True,
            "extracted_text": "\n\n".join(all_text),
            "files": [
                {
                    "filename": f['filename'],
                    "type": f['type'],
                    "content_preview": f['content'][:500] + "..." if len(f['content']) > 500 else f['content']
                }
                for f in processed_files
            ]
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok", "model": settings.kimi_text_model}


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
