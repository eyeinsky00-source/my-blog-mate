import streamlit as st
from google import genai
from google.genai import types
import urllib.parse
from PIL import Image
import io
import pillow_heif
import re

# --- 아이폰 HEIC 이미지 인식 지원 ---
pillow_heif.register_heif_opener()

# --- 1. 기본 웹사이트 설정 ---
st.set_page_config(page_title="블로그 작성 도우미", page_icon="📸", layout="centered")
st.title("📸 무오류 블로그 메이트")
st.write("에러 없이 빠르고 안정적으로! AI가 팩트체크를 마치고 완벽한 포스팅을 만들어 줍니다.")

# --- 2. API 키 설정 ---
import os
# 서버의 환경변수나 시스템에서 안전하게 키를 가져옵니다.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- 3. 사용자 입력 폼 (UI) ---
category = st.selectbox("블로그 카테고리 선택", [
    "제품 사용기 (IT/리뷰)", 
    "장소 방문기 (맛집/여행)", 
    "책 감상 (도서 리뷰)", 
    "영화 감상 (영화 리뷰)",
    "음악 감상 (음원/앨범 리뷰)", 
    "기타 일상"
])

target_info = ""
if category == "제품 사용기 (IT/리뷰)":
    target_info = st.text_input("리뷰할 제품명 (예: 아이폰 15 프로)")
elif category == "장소 방문기 (맛집/여행)":
    target_info = st.text_input("방문한 장소명 (예: 제주도 몽상드애월)")
elif category in ["책 감상 (도서 리뷰)", "영화 감상 (영화 리뷰)", "음악 감상 (음원/앨범 리뷰)"]:
    target_info = st.text_input("리뷰할 제목 및 관련 정보 (예: 인터스텔라, 소년이 온다 한강, Supernova 에스파)")

draft = st.text_area("초안 메모 입력", height=150, placeholder="사실관계가 헷갈려도 괜찮습니다. 생각나는 대로 편하게 적어보세요.")
uploaded_photos = st.file_uploader("직접 찍은 사진 첨부 (여러 장 선택 가능)", accept_multiple_files=True, type=['jpg', 'jpeg', 'png', 'heic'])

# --- helper 함수 ---
def get_image_part(uploaded_file):
    if uploaded_file is not None:
        bytes_data = uploaded_file.getvalue()
        img = Image.open(io.BytesIO(bytes_data))
        img = img.convert("RGB")
        output = io.BytesIO()
        img.save(output, format="JPEG")
        converted_bytes = output.getvalue()
        return types.Part.from_bytes(data=converted_bytes, mime_type="image/jpeg")
    return None

# --- 4. AI 글쓰기 엔진 ---
if st.button("안정적인 블로그 작성 시작", type="primary"):
    if not draft:
        st.warning("초안을 입력해 주세요.")
    else:
        with st.spinner("사실관계를 확인하고 글을 다듬는 중입니다... (이미지 에러 없음!)"):
            try:
                # 인터넷 이미지 안내 문구 (검색 다운로드 대신 빈칸 태그만 지시)
                internet_image_guide = ""
                if category == "책 감상 (도서 리뷰)":
                    internet_image_guide = "\n- 글 맨 위쪽이나 책 소개 부분에 반드시 [인터넷 사진 1 삽입] 태그를 적어주세요. (책 표지용)"
                elif category == "영화 감상 (영화 리뷰)":
                    internet_image_guide = "\n- 내용 전개에 어울리는 위치에 [인터넷 사진 1 삽입](포스터용), [인터넷 사진 2 삽입](스틸컷용) 태그를 적어주세요."
                elif category == "음악 감상 (음원/앨범 리뷰)":
                    internet_image_guide = "\n- 내용 전개에 어울리는 위치에 [인터넷 사진 1 삽입](앨범 커버용), [인터넷 사진 2 삽입](아티스트용) 태그를 적어주세요."

                client = genai.Client(api_key=GEMINI_API_KEY)
                search_tool = types.Tool(google_search=types.GoogleSearch())
                model_contents = []
                
                prompt = f"""
                당신은 네이버 블로그를 운영하는 베테랑 개인 블로거입니다. 

                [작성 환경]
                - 카테고리: {category}
                - 주요 대상: {target_info}

                [⚠️ 핵심 지침: 팩트체크 및 자동 교정 (Fact-Checking)]
                사용자의 초안은 기억에 의존해 작성되었으므로 정보가 부정확할 수 있습니다. 
                1. 구글 검색 기능을 활용해 초안에 언급된 정보(제품 스펙, 가격, 감독, 배우, 출판연도, 발매일 등)를 철저히 검증하세요.
                2. 사용자가 적은 정보가 틀렸다면, 원본을 쓰지 말고 **정확한 최신 정보로 자연스럽게 수정**하여 글을 작성하세요.

                [⚠️ 절대 엄수 지침 (네이버 블로그 복사 최적화 및 AI 느낌 지우기)]
                1. **마크다운 기호 전면 금지**: 별표(**), 샵(#) 등 마크다운 문법을 절대 사용하지 마세요.
                2. **소제목 강조 방식**: 마크다운 대신 깔끔한 기호를 사용해 구분하세요. (예: ■ 직접 써보며 느낀 장단점)
                3. **가독성 높은 줄바꿈**: 문단과 문단 사이, 소제목과 본문 사이에는 반드시 빈 줄을 하나씩 넣어주세요.
                4. 뻔한 이모지 남발 금지. 담백한 문체를 유지하세요.
                
                [📷 이미지 배치 중요 지침]
                - 사용자가 직접 찍어 올린 사진이 있다면, 문맥에 맞게 [사진 1 삽입], [사진 2 삽입] 태그를 배치하세요.{internet_image_guide}

                [카테고리별 추가 미션]
                - '제품 사용기': 구글 검색을 통해 최신 공식 스펙을 본문에 녹여내세요.
                - '장소 방문기': 하단에 정확한 도로명 주소를 적고, "[네이버 지도에서 위치 보기](https://map.naver.com/v5/search/{urllib.parse.quote(target_info)})" 링크를 추가하세요.
                - '책 감상': 저자, 출판사, 출판일 정보를 확인하여 책 소개란을 구성하세요.
                - '영화 감상': 감독, 주요 출연진, 개봉일 정보를 구성하세요.
                - '음악 감상': 아티스트, 발매일, 장르, 앨범 소개 등 곡의 배경 정보를 구성하세요.

                [사용자 초안]
                {draft}
                """
                
                model_contents.append(prompt)

                if uploaded_photos:
                    for i, uploaded_file in enumerate(uploaded_photos):
                        img_part = get_image_part(uploaded_file)
                        if img_part:
                            model_contents.append(f"[직접 찍은 사진 {i+1}의 내용 분석:]")
                            model_contents.append(img_part)

                response = client.models.generate_content(
                    model='gemini-2.5-pro',
                    contents=model_contents,
                    config=types.GenerateContentConfig(
                        tools=[search_tool],
                        temperature=0.7
                    )
                )
                generated_text = response.text

                # --- 5. 텍스트 후처리 (이미지 플레이스홀더로 변환) ---
                # 인터넷 사진 태그를 안내 박스로 변환
                generated_text = re.sub(r"\[인터넷 사진 1 삽입\]", f"\n\n> 🖼️ **[여기에 구글에서 복사한 메인 사진(표지/포스터/앨범)을 붙여넣으세요 (Ctrl+V)]**\n\n", generated_text)
                generated_text = re.sub(r"\[인터넷 사진 2 삽입\]", f"\n\n> 🖼️ **[여기에 구글에서 복사한 추가 사진(스틸컷/아티스트)을 붙여넣으세요 (Ctrl+V)]**\n\n", generated_text)

                # 직접 찍은 사진 태그를 안내 박스로 변환
                if uploaded_photos:
                    for i in range(len(uploaded_photos)):
                        placeholder = f"\n\n> 📷 **[여기에 직접 찍은 사진 {i+1}을 마우스로 끌어다 놓으세요]**\n\n"
                        generated_text = generated_text.replace(f"[사진 {i+1} 삽입]", placeholder)

                # --- 6. 결과 화면 출력 ---
                st.success("포스팅 작성이 완료되었습니다! (에러 방지 적용)")
                
                # 구글 이미지 검색 퀵 링크 제공 (문화 리뷰일 경우에만)
                if category in ["책 감상 (도서 리뷰)", "영화 감상 (영화 리뷰)", "음악 감상 (음원/앨범 리뷰)"]:
                    st.info("💡 **이미지 가져오기 팁:** 아래 링크를 눌러 마음에 드는 사진을 '우클릭 -> 이미지 복사' 한 뒤, 네이버 블로그에 붙여넣기 하세요!")
                    col1, col2 = st.columns(2)
                    
                    if category == "책 감상 (도서 리뷰)":
                        query_url = f"https://www.google.com/search?tbm=isch&q={urllib.parse.quote(target_info + ' 책 표지')}"
                        col1.markdown(f"### [🔍 '{target_info}' 책 표지 검색하기]({query_url})")
                    elif category == "영화 감상 (영화 리뷰)":
                        q1 = f"https://www.google.com/search?tbm=isch&q={urllib.parse.quote(target_info + ' 포스터')}"
                        q2 = f"https://www.google.com/search?tbm=isch&q={urllib.parse.quote(target_info + ' 스틸컷')}"
                        col1.markdown(f"### [🔍 '{target_info}' 포스터 검색]({q1})")
                        col2.markdown(f"### [🔍 '{target_info}' 스틸컷 검색]({q2})")
                    elif category == "음악 감상 (음원/앨범 리뷰)":
                        q1 = f"https://www.google.com/search?tbm=isch&q={urllib.parse.quote(target_info + ' 앨범 커버')}"
                        q2 = f"https://www.google.com/search?tbm=isch&q={urllib.parse.quote(target_info + ' 아티스트')}"
                        col1.markdown(f"### [🔍 '{target_info}' 앨범 커버 검색]({q1})")
                        col2.markdown(f"### [🔍 '{target_info}' 아티스트 검색]({q2})")
                
                st.markdown("---")
                st.subheader("👁️ 블로그 미리보기 (드래그 복사 권장)")
                st.markdown(generated_text)
                
                # --- 7. 원클릭 복사 영역 ---
                st.markdown("---")
                st.subheader("📋 원본 텍스트 원클릭 복사")
                st.code(generated_text, language="text")
                
            except Exception as e:
                st.error(f"작성 중 오류가 발생했습니다: {e}")