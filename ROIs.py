class ROI: 
    x = 736
    y = 717
    w = 449
    h = 51
    img_size = (108, 36)
    
    # These location values are relative to the ROI
    drop_button_location = (0, 0)
    # Three positions when drop button 'X' is present and not, and
    back_button_location1 = (337, 6)
    back_button_location2 = (258, 6)
    
    sort_button_location = (0, 0)

class AbilitiesROI:
    x = 988
    y = 783
    w = 121
    h = 54
    # dimensions, scale, width/height, whatever you wanna call it
    img_size = (108, 36) 
    
    back_button_location = (6, 10)
    
class InventoryROI:
    x = 1070
    y = 1023
    w = 115
    h = 45
    
    hold_button_location = (6, 3)
    
    img_size = (100, 39)
    
class SortbuttonROI:
    x = 374
    y = 710
    w = 165
    h = 70
    
    sort_button_location = (11, 8)
    
    img_size = (139, 50)