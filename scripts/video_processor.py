#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
餐饮视频知识提取系统
批量处理勇哥餐饮视频，提取知识并扩充知识库
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# 尝试导入Whisper（可选）
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    print("⚠️ Whisper未安装，语音识别功能将不可用")

# 尝试导入pydub（用于音频处理）
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

class VideoKnowledgeExtractor:
    """视频知识提取器"""
    
    def __init__(self, video_dir: str, output_dir: str = "./video_knowledge"):
        self.video_dir = Path(video_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.status_file = self.output_dir / "transcription_status.json"
        self.status = self.load_status()
        
        # 课程分类映射
        self.category_mapping = {
            "1.先导篇": "先导篇",
            "2.餐饮选址实用指南": "选址指南",
            "3创业2.0课程": "创业2.0",
            "4创业1.0课程": "创业1.0",
            "5小吃福利课程": "小吃制作",
            "8同城引流课程": "同城引流",
            "9拍摄和剪辑": "拍摄剪辑"
        }
        
        # Whisper模型
        self.whisper_model = None

    def load_status(self) -> Dict:
        if not self.status_file.exists():
            return {"updated_at": None, "videos": {}}
        try:
            return json.loads(self.status_file.read_text(encoding="utf-8"))
        except Exception:
            return {"updated_at": None, "videos": {}}

    def save_status(self):
        self.status["updated_at"] = datetime.now().isoformat()
        self.status_file.write_text(json.dumps(self.status, ensure_ascii=False, indent=2), encoding="utf-8")

    def result_path_for_video(self, video_info: Dict) -> Path:
        category_dir = self.output_dir / video_info["category"]
        return category_dir / f"{video_info['title']}.json"

    def is_transcribed(self, video_info: Dict) -> bool:
        result_path = self.result_path_for_video(video_info)
        if not result_path.exists():
            return False
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            return False
        return bool(data.get("transcript"))
    
    def load_whisper_model(self, model_name: str = "base"):
        """加载Whisper模型"""
        if not WHISPER_AVAILABLE:
            print("❌ Whisper未安装，无法使用语音识别")
            return False
        
        if self.whisper_model is None:
            print(f"📦 正在加载Whisper模型: {model_name}...")
            self.whisper_model = whisper.load_model(model_name)
        
        return True
    
    def scan_videos(self) -> List[Dict]:
        """扫描所有视频文件"""
        videos = []
        
        print(f"🔍 正在扫描视频目录: {self.video_dir}")
        
        for root, dirs, files in os.walk(self.video_dir):
            for file in files:
                if file.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.flv')):
                    filepath = Path(root) / file
                    relative_path = filepath.relative_to(self.video_dir)
                    
                    # 提取分类
                    category = "其他"
                    for cat_key, cat_name in self.category_mapping.items():
                        if cat_key in str(relative_path.parent):
                            category = cat_name
                            break
                    
                    # 提取标题
                    title = filepath.stem
                    
                    videos.append({
                        "path": str(filepath),
                        "relative_path": str(relative_path),
                        "category": category,
                        "title": title,
                        "filename": file,
                        "size_mb": round(filepath.stat().st_size / (1024 * 1024), 2)
                    })
        
        print(f"✅ 找到 {len(videos)} 个视频文件")
        return videos
    
    def extract_audio_from_video(self, video_path: str, output_audio_path: str) -> bool:
        """从视频中提取音频"""
        if not PYDUB_AVAILABLE:
            print("⚠️ pydub未安装，跳过音频提取")
            return False
        
        try:
            print(f"🎵 正在提取音频: {os.path.basename(video_path)}")
            # 这里需要ffmpeg，实际使用时可能需要其他方式
            return True
        except Exception as e:
            print(f"❌ 音频提取失败: {e}")
            return False
    
    def transcribe_with_whisper(self, video_path: str) -> Optional[Dict]:
        """用Whisper语音识别视频"""
        if not self.load_whisper_model():
            return None
        
        try:
            print(f"🎤 正在语音识别: {os.path.basename(video_path)}")
            result = self.whisper_model.transcribe(video_path, language="zh")
            
            # 整理结果
            transcription = {
                "text": result["text"],
                "segments": [],
                "language": result.get("language", "zh")
            }
            
            for seg in result["segments"]:
                transcription["segments"].append({
                    "start": round(seg["start"], 2),
                    "end": round(seg["end"], 2),
                    "text": seg["text"].strip()
                })
            
            return transcription
        except Exception as e:
            print(f"❌ 语音识别失败: {e}")
            return None
    
    def parse_title_for_knowledge(self, title: str, category: str) -> Dict:
        """从标题中提取初始知识"""
        knowledge = {
            "category": category,
            "title": title,
            "keywords": [],
            "tags": []
        }
        
        # 提取关键词
        keyword_patterns = [
            r"加盟", r"自营", r"选址", r"谈判", r"转让", 
            r"店铺", r"调研", r"商圈", r"客流", r"财务", 
            r"风险", r"选品", r"装修", r"设备", r"食材",
            r"运营", r"推广", r"抖音", r"短视频", r"拍摄",
            r"剪辑", r"小吃", r"早餐", r"粉面", r"社交"
        ]
        
        for pattern in keyword_patterns:
            if re.search(pattern, title):
                knowledge["keywords"].append(pattern)
        
        # 自动标签
        if "加盟" in title or "自营" in title:
            knowledge["tags"].append("经营模式")
        if "选址" in title or "商圈" in title:
            knowledge["tags"].append("选址")
        if "财务" in title or "风险" in title:
            knowledge["tags"].append("财务管理")
        if "选品" in title or "小吃" in title:
            knowledge["tags"].append("产品")
        if "抖音" in title or "短视频" in title:
            knowledge["tags"].append("营销推广")
        
        return knowledge
    
    def extract_knowledge_from_transcript(self, transcript: Dict) -> Dict:
        """从语音转录中提取结构化知识"""
        text = transcript.get("text", "")
        knowledge = {
            "summary": "",
            "key_points": [],
            "actionable_tips": [],
            "raw_text": text
        }
        
        # 分割句子，提取要点
        sentences = re.split(r'[。！？\n]', text)
        
        for i, sentence in enumerate(sentences[:50]):  # 只处理前50句
            sentence = sentence.strip()
            if len(sentence) < 5:
                continue
            
            # 识别关键句子（包含数字、步骤、建议等）
            if any(keyword in sentence for keyword in ["需要", "应该", "必须", "建议", "注意", "避免", "步骤", "第一", "第二", "第三"]):
                knowledge["key_points"].append(sentence)
            
            # 识别行动建议
            if any(keyword in sentence for keyword in ["可以", "去做", "尝试", "记住", "不要", "别", "一定要"]):
                knowledge["actionable_tips"].append(sentence)
        
        # 生成简单摘要
        if sentences:
            first_paragraphs = [s.strip() for s in sentences[:10] if len(s.strip()) > 10]
            knowledge["summary"] = "".join(first_paragraphs[:3])
        
        return knowledge
    
    def process_single_video(self, video_info: Dict, use_whisper: bool = False) -> Dict:
        """处理单个视频"""
        print(f"\n{'='*60}")
        print(f"📹 处理视频: {video_info['title']}")
        print(f"{'='*60}")
        
        result = {
            "video_info": video_info,
            "processed_at": datetime.now().isoformat(),
            "knowledge": self.parse_title_for_knowledge(video_info["title"], video_info["category"]),
            "transcript": None
        }
        
        # 如果启用Whisper，进行语音识别
        if use_whisper and WHISPER_AVAILABLE:
            transcript = self.transcribe_with_whisper(video_info["path"])
            if transcript:
                result["transcript"] = transcript
                result["knowledge"].update(self.extract_knowledge_from_transcript(transcript))
        
        return result
    
    def batch_process_videos(self, videos: List[Dict], use_whisper: bool = False, limit: Optional[int] = None) -> List[Dict]:
        """批量处理视频"""
        results = []
        videos_to_process = videos[:limit] if limit else videos
        
        print(f"\n🚀 开始批量处理 {len(videos_to_process)} 个视频...\n")
        
        for i, video in enumerate(videos_to_process, 1):
            print(f"\n进度: [{i}/{len(videos_to_process)}]")
            try:
                if use_whisper and self.is_transcribed(video):
                    print(f"⏭️ 已转写，跳过: {video['title']}")
                    existing = json.loads(self.result_path_for_video(video).read_text(encoding="utf-8"))
                    results.append(existing)
                    continue
                result = self.process_single_video(video, use_whisper=use_whisper)
                results.append(result)
                
                # 保存单个结果
                self.save_single_result(result)
                key = str(video["relative_path"])
                self.status["videos"][key] = {
                    "title": video["title"],
                    "category": video["category"],
                    "path": video["path"],
                    "status": "transcribed" if result.get("transcript") else "indexed_only",
                    "processed_at": result.get("processed_at"),
                }
                self.save_status()
                
            except Exception as e:
                print(f"❌ 处理视频 {video['title']} 失败: {e}")
                key = str(video["relative_path"])
                self.status["videos"][key] = {
                    "title": video["title"],
                    "category": video["category"],
                    "path": video["path"],
                    "status": "failed",
                    "error": str(e),
                    "processed_at": datetime.now().isoformat(),
                }
                self.save_status()
        
        return results
    
    def save_single_result(self, result: Dict):
        """保存单个视频的处理结果"""
        category_dir = self.output_dir / result["video_info"]["category"]
        category_dir.mkdir(exist_ok=True)
        
        filepath = self.result_path_for_video(result["video_info"])
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"💾 已保存: {filepath}")
    
    def compile_master_knowledge_base(self, results: List[Dict]) -> Dict:
        """编译主知识库"""
        print(f"\n📚 正在编译知识库...")
        
        master_kb = {
            "compiled_at": datetime.now().isoformat(),
            "total_videos": len(results),
            "categories": {},
            "all_keywords": set(),
            "all_tags": set(),
            "videos": []
        }
        
        # 按分类整理
        for result in results:
            category = result["video_info"]["category"]
            
            if category not in master_kb["categories"]:
                master_kb["categories"][category] = {
                    "videos": [],
                    "keywords": set(),
                    "tags": set()
                }
            
            master_kb["categories"][category]["videos"].append(result["video_info"]["title"])
            
            # 收集关键词和标签
            for keyword in result["knowledge"].get("keywords", []):
                master_kb["categories"][category]["keywords"].add(keyword)
                master_kb["all_keywords"].add(keyword)
            
            for tag in result["knowledge"].get("tags", []):
                master_kb["categories"][category]["tags"].add(tag)
                master_kb["all_tags"].add(tag)
            
            master_kb["videos"].append({
                "title": result["video_info"]["title"],
                "category": category,
                "knowledge": result["knowledge"]
            })
        
        # 转换集合为列表
        master_kb["all_keywords"] = list(master_kb["all_keywords"])
        master_kb["all_tags"] = list(master_kb["all_tags"])
        
        for cat in master_kb["categories"]:
            master_kb["categories"][cat]["keywords"] = list(master_kb["categories"][cat]["keywords"])
            master_kb["categories"][cat]["tags"] = list(master_kb["categories"][cat]["tags"])
        
        # 保存主知识库
        master_file = self.output_dir / "master_knowledge_base.json"
        with open(master_file, "w", encoding="utf-8") as f:
            json.dump(master_kb, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 知识库已编译: {master_file}")
        return master_kb

    def load_all_saved_results(self) -> List[Dict]:
        """读取输出目录下所有已保存的视频 JSON，用于重建完整 master。"""
        results = []
        for file_path in self.output_dir.glob("**/*.json"):
            if file_path.name in {"master_knowledge_base.json", "transcription_status.json"}:
                continue
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(data, dict) and "video_info" in data:
                results.append(data)
        return results
    
    def generate_markdown_knowledge_base(self, master_kb: Dict, output_file: str = "勇哥餐饮知识库.md"):
        """生成Markdown格式的知识库"""
        print(f"📝 正在生成Markdown知识库...")
        
        md_content = f"# 勇哥餐饮知识库\n\n"
        md_content += f"**创建时间**: {master_kb['compiled_at']}\n\n"
        md_content += f"**视频总数**: {master_kb['total_videos']}\n\n"
        md_content += "---\n\n"
        
        # 分类概览
        md_content += "## 📁 课程分类\n\n"
        for category, info in master_kb["categories"].items():
            md_content += f"### {category}\n"
            md_content += f"- 视频数量: {len(info['videos'])}\n"
            md_content += f"- 关键词: {', '.join(info['keywords'])}\n"
            md_content += f"- 标签: {', '.join(info['tags'])}\n\n"
        
        md_content += "---\n\n"
        
        # 详细视频列表
        md_content += "## 📹 视频列表\n\n"
        for video in master_kb["videos"]:
            md_content += f"### {video['title']}\n"
            md_content += f"- **分类**: {video['category']}\n"
            md_content += f"- **关键词**: {', '.join(video['knowledge'].get('keywords', []))}\n"
            md_content += f"- **标签**: {', '.join(video['knowledge'].get('tags', []))}\n\n"
        
        # 保存文件
        output_path = self.output_dir / output_file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        print(f"✅ Markdown知识库已生成: {output_path}")
        return output_path
    
    def update_开店Agent知识库(self, master_kb: Dict, existing_kb_path: str = "./开店Agent知识库.md"):
        """更新开店Agent知识库"""
        existing_path = Path(existing_kb_path)
        if not existing_path.exists():
            print(f"⚠️ 现有知识库不存在: {existing_kb_path}")
            return None
        
        # 读取现有知识库
        with open(existing_path, "r", encoding="utf-8") as f:
            existing_content = f.read()
        
        # 添加新内容
        update_content = "\n\n---\n\n"
        update_content += "## 🔄 新增：勇哥餐饮视频知识库 (自动提取)\n\n"
        update_content += f"### 新增视频总数: {master_kb['total_videos']}\n\n"
        
        # 按分类整理
        for category, info in master_kb["categories"].items():
            update_content += f"#### {category}\n"
            update_content += f"- **包含视频**: {', '.join(info['videos'])}\n"
            update_content += f"- **关键词**: {', '.join(info['keywords'])}\n"
            update_content += f"- **标签**: {', '.join(info['tags'])}\n\n"
        
        # 写入
        updated_path = self.output_dir / "开店Agent知识库_增强版.md"
        with open(updated_path, "w", encoding="utf-8") as f:
            f.write(existing_content + update_content)
        
        print(f"✅ 已更新开店Agent知识库: {updated_path}")
        return updated_path

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="餐饮视频知识提取系统")
    project_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--video-dir", "-v", default=str(project_root / "资料" / "餐饮"), help="视频目录")
    parser.add_argument("--output-dir", "-o", default=str(project_root / "knowledge_base" / "video_knowledge"), help="输出目录")
    parser.add_argument("--use-whisper", "-w", action="store_true", help="使用Whisper语音识别")
    parser.add_argument("--limit", "-l", type=int, default=None, help="处理视频数量限制")
    parser.add_argument("--whisper-model", default="base", help="Whisper模型大小 (tiny/base/small/medium/large)")
    parser.add_argument("--audit", action="store_true", help="只审计视频转写状态，不处理")
    parser.add_argument("--rebuild-master", action="store_true", help="只从已保存 JSON 重建 master/Markdown，不处理视频")
    parser.add_argument("--title-contains", default=None, help="只处理标题包含指定文本的视频")
    
    args = parser.parse_args()
    
    # 创建提取器
    extractor = VideoKnowledgeExtractor(args.video_dir, args.output_dir)
    
    # 设置Whisper模型（如果使用）
    if args.use_whisper:
        extractor.load_whisper_model(args.whisper_model)
    
    # 扫描视频
    videos = extractor.scan_videos()
    
    if not videos:
        print("❌ 没有找到视频文件")
        return

    if args.title_contains:
        videos = [video for video in videos if args.title_contains in video["title"]]
        print(f"🔎 标题过滤后剩余 {len(videos)} 个视频")
        if not videos:
            return

    if args.audit:
        transcribed = sum(1 for video in videos if extractor.is_transcribed(video))
        print(json.dumps({
            "video_dir": str(extractor.video_dir),
            "output_dir": str(extractor.output_dir),
            "total": len(videos),
            "transcribed": transcribed,
            "not_transcribed": len(videos) - transcribed,
            "status_file": str(extractor.status_file),
        }, ensure_ascii=False, indent=2))
        return

    if args.rebuild_master:
        all_results = extractor.load_all_saved_results()
        master_kb = extractor.compile_master_knowledge_base(all_results)
        extractor.generate_markdown_knowledge_base(master_kb)
        extractor.update_开店Agent知识库(master_kb, str(project_root / "knowledge_base" / "开店Agent知识库.md"))
        print(json.dumps({"rebuilt": True, "videos": len(all_results)}, ensure_ascii=False, indent=2))
        return
    
    # 批量处理
    results = extractor.batch_process_videos(videos, use_whisper=args.use_whisper, limit=args.limit)
    
    # 编译主知识库：必须基于所有已保存结果，不能只基于本次处理的 limit 子集
    all_results = extractor.load_all_saved_results()
    master_kb = extractor.compile_master_knowledge_base(all_results)
    
    # 生成Markdown
    extractor.generate_markdown_knowledge_base(master_kb)
    
    # 更新开店Agent知识库
    extractor.update_开店Agent知识库(master_kb, str(project_root / "knowledge_base" / "开店Agent知识库.md"))
    
    print(f"\n{'='*60}")
    print("✅ 处理完成!")
    print(f"📊 本次处理视频数: {len(results)}")
    print(f"📊 已入库视频数: {len(all_results)}")
    print(f"📁 输出目录: {extractor.output_dir}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
