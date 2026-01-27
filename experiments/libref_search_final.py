"""
RESEARCH: Exhaustive LibRef Model Search
Searching all categories and libraries in LibRef for 'Mixer'
"""
import win32com.client as win32
import time

def search_libref():
    try:
        aspen = win32.Dispatch("Apwn.Document")
        # Ensure it's initialized
        aspen.InitNew()
        aspen.SuppressDialogs = 1
        time.sleep(5)
        
        libref = aspen.LibRef
        count_libs = libref.CountLibs
        print(f"Libraries: {count_libs}")
        
        # We know Category 0 is 'Mixers/Splitters' from previous run
        # Let's try to list elements in that category
        # But 'Elements' property on LibRef depends on the CURRENT selection
        
        for i in range(count_libs):
            print(f"Checking Library {i}: {libref.LibraryName(i)}")
            
            # Categories loop
            for cat_idx in range(20): # Check first 20 categories
                try:
                    cat_name = libref.CategoryName(cat_idx)
                    if not cat_name: continue
                    
                    print(f"  Category {cat_idx}: {cat_name}")
                    
                    # Mark category as selected?
                    # Some sources say libref.CategorySelected(cat_idx) = True
                    # Let's try to see the Elements now
                    try:
                        els = libref.Elements
                        if els:
                             print(f"    Elements in category '{cat_name}': {els.Count}")
                             for e_idx in range(els.Count):
                                  item = els.Item(e_idx)
                                  if "Mixer" in item.Name:
                                       print(f"      [FOUND] Name: {item.Name} | Value: {item.Value if hasattr(item, 'Value') else 'N/A'}")
                    except:
                        pass
                except:
                    break

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    search_libref()
